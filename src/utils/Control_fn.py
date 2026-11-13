import os 

def _get_unique_filepath(directory, filename):
    base_path = os.path.join(directory, filename)
    if not os.path.exists(base_path):
        return base_path

    from tkinter import messagebox
    user_choice = messagebox.askyesno(
        "File Already Exists", 
        f"The file '{filename}' already exists in your downloads folder.\n\nDo you want to download it again?"
    )
    
    if not user_choice:
        raise FileExistsError("Download cancelled because file already exists.")

    name_without_ext, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{name_without_ext} ({counter}){ext}"
        new_path = os.path.join(directory, new_filename)
        if not os.path.exists(new_path):
            return new_path
        counter += 1