#!/usr/bin/env python3
"""
Simple Python GUI application that displays "hello"
"""

import tkinter as tk


def main():
    # Create the main window
    root = tk.Tk()
    root.title("Hello Application")
    root.geometry("400x300")

    # Create a label with "hello" text
    label = tk.Label(
        root,
        text="hello",
        font=("Arial", 48),
        fg="blue"
    )
    label.pack(expand=True)

    # Start the GUI event loop
    root.mainloop()


if __name__ == "__main__":
    main()
