"""Keep process titles anonymous only for this task's explicitly opted-in workers."""

import os

if os.environ.get("DSH_MASK_PROCESS_TITLE") == "1":
    import setproctitle

    original_title = setproctitle.setproctitle

    def task_title(_title):
        original_title("python")

    setproctitle.setproctitle = task_title
    task_title("python")
