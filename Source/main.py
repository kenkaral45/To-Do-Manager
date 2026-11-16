import sys
from PyQt6.QtWidgets import QApplication
from mainwindow import TodoManager
from style import apply_theme

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("To-Do Manager")
    app.setOrganizationName("TodoManagerCompany")
    apply_theme(app)

    win = TodoManager()
    win.show()
    sys.exit(app.exec())


