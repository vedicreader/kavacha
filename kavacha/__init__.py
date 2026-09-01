__version__ = "0.0.1"

# The names a caller reaches for. `spec`, `build`, `bundle` and `probe` need nothing but fastcore,
# so describing an app and asking what a build would do works on a machine that cannot build one.
from .probe import backend, framework_python, is_framework, running_from, shell_ready, wait_for_http
from .spec import App, doc_types, mypyc_modules, tree
from .bundle import finish, frozen_distribution, graft, link_duplicates, strip_zip
from .build import build, check, lock_requirements, read_stamp, write_stamp

__all__ = ['backend', 'framework_python', 'is_framework', 'running_from', 'shell_ready',
           'wait_for_http', 'App', 'doc_types', 'mypyc_modules', 'tree', 'finish',
           'frozen_distribution', 'graft', 'link_duplicates', 'strip_zip', 'build', 'check',
           'lock_requirements', 'read_stamp', 'write_stamp']
