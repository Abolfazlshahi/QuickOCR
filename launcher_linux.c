#define _GNU_SOURCE
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    char exe[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (len <= 0) return 1;
    exe[len] = '\0';
    char *dir = dirname(exe);

    char py[PATH_MAX], app[PATH_MAX], mdl[PATH_MAX];
    snprintf(py, sizeof(py), "%s/runtime/bin/python3", dir);
    if (access(py, X_OK) != 0)
        snprintf(py, sizeof(py), "%s/.venv/bin/python", dir);
    if (access(py, X_OK) != 0)
        snprintf(py, sizeof(py), "python3");

    snprintf(app, sizeof(app), "%s/app.py", dir);
    snprintf(mdl, sizeof(mdl), "%s/models", dir);
    if (!getenv("LITEPARSE_MODEL_DIR") && !getenv("APPIMAGE"))
        setenv("LITEPARSE_MODEL_DIR", mdl, 0);

    char **nargv = calloc((size_t)argc + 2, sizeof(char *));
    if (!nargv) return 1;
    nargv[0] = py;
    nargv[1] = app;
    for (int i = 1; i < argc; i++) nargv[i + 1] = argv[i];
    execvp(py, nargv);
    perror("execvp");
    return 1;
}
