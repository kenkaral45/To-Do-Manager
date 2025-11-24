import sys
from PyQt6.QtWidgets import QApplication
from mainwindow import TodoManager

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("To-Do Manager")
    app.setOrganizationName("TodoManagerCompany")

    win = TodoManager()
    win.show()
    sys.exit(app.exec())
