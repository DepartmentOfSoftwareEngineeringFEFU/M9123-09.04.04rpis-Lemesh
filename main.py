import tkinter as tk
import sqlite3
from gui import SubjectSelectorApp
import ttkbootstrap as tb
from ttkbootstrap.constants import *

if __name__ == "__main__":

    conn = sqlite3.connect('terms.db')
    cursor = conn.cursor()

    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    for name, sql in cursor.fetchall():
        print(f"Table: {name}\nSQL: {sql}\n")

    conn.close()

    root = tb.Window(themename="minty")
    root.geometry("450x500")

    root.resizable(False, False)
    
    window_width = 450
    window_height = 500

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)

    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

    app = SubjectSelectorApp(root)
    root.mainloop()