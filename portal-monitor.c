#define _GNU_SOURCE
#include <gio/gio.h>
#include <gio/gunixfdlist.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>

/* Only the explicitly preloaded host process is affected. Authentication,
 * transport, and input injection remain implemented by the Google binary. */
static GMutex lock;
static char *start_path;
static const char *token_path(void) { return g_getenv("CRD_MONITOR_TOKEN_FILE"); }

static char *read_token(void) {
    const char *path = token_path();
    if (!path) return NULL;
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return NULL;
    struct stat st;
    if (fstat(fd, &st) || st.st_uid != getuid() || (st.st_mode & 077) ||
        !S_ISREG(st.st_mode) || st.st_size < 1 || st.st_size > 4096) {
        close(fd); return NULL;
    }
    char *value = g_malloc(st.st_size + 1);
    ssize_t count = read(fd, value, st.st_size);
    close(fd);
    if (count != st.st_size) { g_free(value); return NULL; }
    value[count] = 0;
    return value;
}

static void save_token(const char *value) {
    const char *path = token_path();
    if (!path || !value || !*value) return;
    GError *error = NULL;
    if (!g_file_set_contents_full(path, value, -1,
            G_FILE_SET_CONTENTS_CONSISTENT | G_FILE_SET_CONTENTS_DURABLE,
            0600, &error)) {
        g_warning("crd-monitor: permission token could not be saved: %s", error->message);
        g_clear_error(&error);
    } else {
        g_message("crd-monitor: persistent portal permission saved");
    }
}

static GDBusMessage *observe_response(GDBusConnection *connection,
        GDBusMessage *message, gboolean incoming, gpointer data) {
    (void)connection; (void)data;
    if (!incoming || g_dbus_message_get_message_type(message) != G_DBUS_MESSAGE_TYPE_SIGNAL ||
        g_strcmp0(g_dbus_message_get_interface(message), "org.freedesktop.portal.Request") ||
        g_strcmp0(g_dbus_message_get_member(message), "Response")) return message;
    g_mutex_lock(&lock);
    gboolean matches = start_path && !g_strcmp0(start_path, g_dbus_message_get_path(message));
    g_mutex_unlock(&lock);
    GVariant *body = g_dbus_message_get_body(message);
    if (!matches || !body || !g_variant_is_of_type(body, G_VARIANT_TYPE("(ua{sv})"))) return message;
    guint code; GVariant *results;
    g_variant_get(body, "(u@a{sv})", &code, &results);
    if (code == 0) {
        const char *token = NULL;
        if (g_variant_lookup(results, "restore_token", "&s", &token)) save_token(token);
        else g_message("crd-monitor: session approved; portal returned no persistent token");
    } else g_message("crd-monitor: portal permission was not granted (response %u)", code);
    g_variant_unref(results);
    return message;
}

static GVariant *transform(GDBusConnection *connection, const char *destination,
        const char *object_path, const char *interface, const char *method,
        GVariant *parameters) {
    if (g_strcmp0(destination, "org.freedesktop.portal.Desktop") ||
        g_strcmp0(object_path, "/org/freedesktop/portal/desktop") ||
        !parameters || !interface || !method) return NULL;
    gboolean devices = !strcmp(interface, "org.freedesktop.portal.RemoteDesktop") && !strcmp(method, "SelectDevices");
    gboolean sources = !strcmp(interface, "org.freedesktop.portal.ScreenCast") && !strcmp(method, "SelectSources");
    gboolean start = !strcmp(interface, "org.freedesktop.portal.RemoteDesktop") && !strcmp(method, "Start");
    if (!devices && !sources && !start) return NULL;
    const char *signature = start ? "(osa{sv})" : "(oa{sv})";
    if (!g_variant_is_of_type(parameters, G_VARIANT_TYPE(signature))) return NULL;
    if (connection) {
        g_mutex_lock(&lock);
        if (!g_object_get_data(G_OBJECT(connection), "crd-monitor-filter")) {
            guint id = g_dbus_connection_add_filter(connection, observe_response, NULL, NULL);
            g_object_set_data(G_OBJECT(connection), "crd-monitor-filter", GUINT_TO_POINTER(id));
        }
        g_mutex_unlock(&lock);
    }
    GVariant *options = g_variant_get_child_value(parameters, start ? 2 : 1);
    if (start) {
        const char *token = NULL;
        const char *unique = connection ? g_dbus_connection_get_unique_name(connection) : ":1.42";
        if (unique && g_variant_lookup(options, "handle_token", "&s", &token)) {
            char *sender = g_strdup(unique + 1);
            for (char *p = sender; *p; p++) if (*p == '.') *p = '_';
            g_mutex_lock(&lock);
            g_free(start_path);
            start_path = g_strdup_printf("/org/freedesktop/portal/desktop/request/%s/%s", sender, token);
            g_mutex_unlock(&lock);
            g_free(sender);
        }
        g_variant_unref(options);
        return NULL;
    }
    GVariantDict dict;
    g_variant_dict_init(&dict, options);
    if (devices) {
        g_variant_dict_insert(&dict, "persist_mode", "u", 2u);
        char *token = read_token();
        if (token) {
            g_variant_dict_insert(&dict, "restore_token", "s", token);
            g_free(token);
            g_message("crd-monitor: restoring saved portal permission");
        } else g_message("crd-monitor: requesting initial persistent portal permission");
    } else {
        /* Physical monitor only: no virtual monitor and no separate session. */
        g_variant_dict_insert(&dict, "types", "u", 1u);
        g_message("crd-monitor: selecting the existing physical monitor");
    }
    GVariant *session = g_variant_get_child_value(parameters, 0);
    GVariant *result = g_variant_ref_sink(g_variant_new("(@o@a{sv})", session, g_variant_dict_end(&dict)));
    g_variant_unref(options);
    return result;
}

void g_dbus_connection_call_with_unix_fd_list(GDBusConnection *connection,
        const gchar *destination, const gchar *object_path, const gchar *interface,
        const gchar *method, GVariant *parameters, const GVariantType *reply_type,
        GDBusCallFlags flags, gint timeout, GUnixFDList *fd_list,
        GCancellable *cancellable, GAsyncReadyCallback callback, gpointer user_data) {
    typedef void (*Function)(GDBusConnection *, const gchar *, const gchar *, const gchar *,
        const gchar *, GVariant *, const GVariantType *, GDBusCallFlags, gint,
        GUnixFDList *, GCancellable *, GAsyncReadyCallback, gpointer);
    Function real = (Function)dlsym(RTLD_NEXT, "g_dbus_connection_call_with_unix_fd_list");
    GVariant *changed = transform(connection, destination, object_path, interface, method, parameters);
    real(connection, destination, object_path, interface, method, changed ? changed : parameters,
        reply_type, flags, timeout, fd_list, cancellable, callback, user_data);
    if (changed) g_variant_unref(changed);
}

void g_dbus_connection_call(GDBusConnection *connection,
        const gchar *destination, const gchar *object_path, const gchar *interface,
        const gchar *method, GVariant *parameters, const GVariantType *reply_type,
        GDBusCallFlags flags, gint timeout, GCancellable *cancellable,
        GAsyncReadyCallback callback, gpointer user_data) {
    typedef void (*Function)(GDBusConnection *, const gchar *, const gchar *, const gchar *,
        const gchar *, GVariant *, const GVariantType *, GDBusCallFlags, gint,
        GCancellable *, GAsyncReadyCallback, gpointer);
    Function real = (Function)dlsym(RTLD_NEXT, "g_dbus_connection_call");
    GVariant *changed = transform(connection, destination, object_path, interface, method, parameters);
    real(connection, destination, object_path, interface, method, changed ? changed : parameters,
        reply_type, flags, timeout, cancellable, callback, user_data);
    if (changed) g_variant_unref(changed);
}

#ifdef SELF_TEST
static GVariant *request(const char *method, const char *interface, GVariant *p) {
    return transform(NULL, "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", interface, method, p);
}
int main(void) {
    const char *rd = "org.freedesktop.portal.RemoteDesktop";
    const char *sc = "org.freedesktop.portal.ScreenCast";
    GVariantBuilder b;
    g_variant_builder_init(&b, G_VARIANT_TYPE_VARDICT);
    g_variant_builder_add(&b, "{sv}", "types", g_variant_new_uint32(4));
    g_variant_builder_add(&b, "{sv}", "cursor_mode", g_variant_new_uint32(4));
    GVariant *p = g_variant_ref_sink(g_variant_new("(oa{sv})", "/session/test", &b));
    GVariant *r = request("SelectSources", sc, p);
    GVariant *o = g_variant_get_child_value(r, 1); guint v = 0;
    g_assert(g_variant_lookup(o,"types","u",&v)); g_assert_cmpuint(v,==,1);
    g_assert(g_variant_lookup(o,"cursor_mode","u",&v)); g_assert_cmpuint(v,==,4);
    g_variant_unref(o); g_variant_unref(r);
    g_assert_null(request("SelectDevices", "unrelated.interface", p));
    GVariant *bad = g_variant_ref_sink(g_variant_new("(s)", "invalid"));
    g_assert_null(request("SelectDevices", rd, bad)); g_variant_unref(bad);
    r = request("SelectDevices", rd, p); o = g_variant_get_child_value(r,1);
    g_assert(g_variant_lookup(o,"persist_mode","u",&v)); g_assert_cmpuint(v,==,2);
    g_variant_unref(o); g_variant_unref(r);
    g_variant_builder_init(&b,G_VARIANT_TYPE_VARDICT);
    g_variant_builder_add(&b,"{sv}","handle_token",g_variant_new_string("test_start"));
    GVariant *s = g_variant_ref_sink(g_variant_new("(osa{sv})","/session/test","",&b));
    request("Start",rd,s);
    GDBusMessage *message = g_dbus_message_new_signal(start_path,"org.freedesktop.portal.Request","Response");
    g_variant_builder_init(&b,G_VARIANT_TYPE_VARDICT);
    g_variant_builder_add(&b,"{sv}","restore_token",g_variant_new_string("test-only-token"));
    g_dbus_message_set_body(message,g_variant_new("(ua{sv})",0u,&b));
    observe_response(NULL,message,TRUE,NULL); g_object_unref(message);
    r=request("SelectDevices",rd,p); o=g_variant_get_child_value(r,1);
    const char *saved=NULL;
    g_assert(g_variant_lookup(o,"restore_token","&s",&saved));
    g_assert_cmpstr(saved,==,"test-only-token");
    g_variant_unref(o); g_variant_unref(r); g_variant_unref(p); g_variant_unref(s);
    g_print("PASS: physical monitor, unchanged cursor, isolation, malformed request, permission persistence and restore\n");
    return 0;
}
#endif
