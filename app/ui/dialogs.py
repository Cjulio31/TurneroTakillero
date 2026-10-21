from PySide6.QtWidgets import QMessageBox, QWidget


def confirm(parent: QWidget | None, title: str, text: str) -> bool:
    """Confirmación Sí/No para acciones de riesgo. "No" es el valor por defecto (Enter/Esc)."""
    box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=parent)
    yes = box.addButton("Sí", QMessageBox.ButtonRole.YesRole)
    no = box.addButton("No", QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no)
    box.setEscapeButton(no)
    box.exec()
    return box.clickedButton() is yes
