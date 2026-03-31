import base64, sys, os, subprocess

def resolve_path(p):
    r = subprocess.run(['cygpath', '-w', p], capture_output=True, text=True)
    return r.stdout.strip()

Q = chr(39)
NL = chr(10)

content = """<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{%% block title %%}Planovani smen{%% endblock %%} | FerMato</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <link href="{{ url_for(QSTATICQ, filename=QcssXstyle.cssQ) }}" rel="stylesheet">
    {%% block extra_css %%}{%% endblock %%}
</head>
<body>
    <div class="app-layout">
        <div class="mobile-topbar">
            <button class="hamburger-btn" onclick="toggleSidebar()" aria-label="Menu">
                <i class="bi bi-list"></i>
            </button>
            <span class="mobile-topbar-brand">FerMato Smeny</span>
        </div>
        <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-brand">
                <div class="sidebar-brand-icon"><i class="bi bi-calendar3"></i></div>
                <div class="sidebar-brand-text">FerMato Smeny<small>Planovani smen</small></div>
            </div>
            <nav class="sidebar-nav">
                <div class="sidebar-section-label">Hlavni</div>
                <a class="sidebar-nav-item {%% if request.endpoint and request.endpoint.startswith(QdashboardQ) %%}active{%% endif %%}" href="{{ url_for(Qdashboard.indexQ) }}">
                    <i class="bi bi-house-door"></i> Prehled
                </a>
                <a class="sidebar-nav-item {%% if request.endpoint and request.endpoint.startswith(QplannerQ) %%}active{%% endif %%}" href="{{ url_for(Qplanner.indexQ) }}">
                    <i class="bi bi-table"></i> Planovac
                </a>
                <a class="sidebar-nav-item {%% if request.endpoint and request.endpoint.startswith(QemployeesQ) %%}active{%% endif %%}" href="{{ url_for(Qemployees.indexQ) }}">
                    <i class="bi bi-people"></i> Zamestnanci
                </a>
                <div class="sidebar-section-label">Sprava</div>
                <a class="sidebar-nav-item {%% if request.endpoint and request.endpoint.startswith(QconstraintsQ) %%}active{%% endif %%}" href="{{ url_for(Qconstraints.indexQ) }}">
                    <i class="bi bi-calendar-x"></i> Absence
                </a>
                <a class="sidebar-nav-item {%% if request.endpoint and request.endpoint.startswith(QsettingsQ) %%}active{%% endif %%}" href="{{ url_for(Qsettings.indexQ) }}">
                    <i class="bi bi-gear"></i> Nastaveni
                </a>
                <a class="sidebar-nav-item {%% if request.endpoint and request.endpoint.startswith(Qimport_csvQ) %%}active{%% endif %%}" href="{{ url_for(Qimport_csv.indexQ) }}">
                    <i class="bi bi-upload"></i> Import
                </a>
            </nav>
            <div class="sidebar-footer">
                <div class="dropdown">
                    <button class="sidebar-user-btn" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                        <div class="sidebar-user-avatar"><i class="bi bi-person"></i></div>
                        <span class="sidebar-user-name">{{ current_user.display_name }}</span>
                        <i class="bi bi-chevron-expand"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end">
                        <li><a class="dropdown-item" href="{{ url_for(Qauth.change_passwordQ) }}"><i class="bi bi-key me-2"></i>Zmena hesla</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li>
                            <form method="POST" action="{{ url_for(Qauth.logoutQ) }}" class="d-inline">
                                <button type="submit" class="dropdown-item"><i class="bi bi-box-arrow-right me-2"></i>Odhlasit se</button>
                            </form>
                        </li>
                    </ul>
                </div>
            </div>
        </aside>
        <main class="main-content">
            {%% block content %%}{%% endblock %%}
        </main>
    </div>
    <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1090;">
        {%% with messages = get_flashed_messages(with_categories=true) %%}
        {%% for category, message in messages %%}
        <div class="toast align-items-center text-bg-{{ QdangerQ if category == QerrorQ else QsuccessQ if category == QsuccessQ else QprimaryQ }} border-0"
             role="alert" aria-live="assertive" aria-atomic="true"
             data-bs-autohide="true" data-bs-delay="3500">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-{{ Qx-circleQ if category == QerrorQ else Qcheck-circleQ if category == QsuccessQ else Qinfo-circleQ }} me-1"></i>
                    {{ message }}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
        {%% endfor %%}
        {%% endwith %%}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script>
    document.addEventListener(QDOMContentLoadedQ, function() {
        document.querySelectorAll(Q.toast-container .toastQ).forEach(function(el) {
            new bootstrap.Toast(el).show();
        });
    });
    document.body.addEventListener(Qhtmx:responseErrorQ, function(evt) {
        if (evt.detail.xhr.status === 401) {
            window.location.href = Q/auth/loginQ;
        }
    });
    function toggleSidebar() {
        var sidebar = document.getElementById(QsidebarQ);
        var overlay = document.getElementById(QsidebarOverlayQ);
        sidebar.classList.toggle(QopenQ);
        overlay.classList.toggle(QshowQ);
    }
    </script>
    {%% block extra_js %%}{%% endblock %%}
</body>
</html>"""

# Replace Q with single quotes and %% with %
content = content.replace('Q', chr(39))
content = content.replace('%%', '%')
content = content.replace('cssXstyle', 'css/style')

wp = resolve_path('/tmp/planovani-smen/app/templates/base.html')
with open(wp, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"base.html written: {len(content)} chars")
