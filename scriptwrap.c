#include <unistd.h>
#include <sys/types.h>

int main(int argc, char *argv[]) {
    setreuid(geteuid(), geteuid());
    setregid(getegid(), getegid());
    return execv("./check_smartmon.py", argv);
}
