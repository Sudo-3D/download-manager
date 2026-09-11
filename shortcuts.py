import tkinter as tk

def handle_global_shortcuts(event, app_instance):
    """
    Keyboard shortcut handler for Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A across Arabic/English keyboard layouts.
    """
    if event.state in [4, 12, 6, 14] or (event.state & 0x0004):
        if event.keycode == 86:
            try:
                clipboard_text = app_instance.root.clipboard_get()
                app_instance.ent_url.insert(tk.INSERT, clipboard_text)
            except tk.TclError:
                pass 
            return "break"
        
        elif event.keycode == 67:
            try:
                selected_text = app_instance.ent_url.selection_get()
                app_instance.root.clipboard_clear()
                app_instance.root.clipboard_append(selected_text)
            except tk.TclError:
                pass 
            return "break"
        
        elif event.keycode == 88:
            try:
                selected_text = app_instance.ent_url.selection_get()
                app_instance.root.clipboard_clear()
                app_instance.root.clipboard_append(selected_text)
                app_instance.ent_url.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass
            return "break"
        
        elif event.keycode == 65:
            app_instance.ent_url.select_range(0, tk.END)
            app_instance.ent_url.icursor(tk.END)
            return "break"

        return "break"