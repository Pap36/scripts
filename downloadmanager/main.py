import tkinter as tk
from tkinter import messagebox, filedialog
import os
from pathlib import Path

# Function to get file extensions and files from the Downloads folder
def get_extensions():
    downloads_path = str(Path.home() / "Downloads")
    files = os.listdir(downloads_path)
    extensions = list(set([os.path.splitext(file)[1].lstrip('.') for file in files if os.path.splitext(file)[1]]))
    return extensions, files

# Function to organize files by extension
def organize_files():
    downloads_path = str(Path.home() / "Downloads")
    extensions, files = get_extensions()
    for ext in extensions:
        folder_path = os.path.join(downloads_path, ext.upper())
        os.makedirs(folder_path, exist_ok=True)
        for file in files:
            if file.endswith(f".{ext}"):
                os.rename(os.path.join(downloads_path, file), os.path.join(folder_path, file))
    messagebox.showinfo("Success", "Files organized by extension!")

# Function to filter files by a specific extension
def filter_files(extension):
    downloads_path = str(Path.home() / "Downloads")
    _, files = get_extensions()
    filtered_files = [file for file in files if file.endswith(f".{extension}")]
    return filtered_files

# UI Setup
class DownloadManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Download Manager")

        # Title label
        self.title_label = tk.Label(root, text="Download Manager", font=("Arial", 16))
        self.title_label.pack(pady=10)

        # Extensions button
        self.extensions_button = tk.Button(root, text="View Extensions", command=self.show_extensions)
        self.extensions_button.pack(pady=5)

        # Organize button
        self.organize_button = tk.Button(root, text="Organize Files", command=organize_files)
        self.organize_button.pack(pady=5)

        # Filter entry and button
        self.filter_label = tk.Label(root, text="Filter by Extension:")
        self.filter_label.pack(pady=5)
        self.filter_entry = tk.Entry(root)
        self.filter_entry.pack(pady=5)
        self.filter_button = tk.Button(root, text="Filter", command=self.filter_action)
        self.filter_button.pack(pady=5)

        # Output box
        self.output_text = tk.Text(root, height=15, width=50)
        self.output_text.pack(pady=10)

    def show_extensions(self):
        extensions, _ = get_extensions()
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, "File Extensions in Downloads:\n")
        self.output_text.insert(tk.END, "\n".join(extensions))

    def filter_action(self):
        extension = self.filter_entry.get().strip()
        if not extension:
            messagebox.showerror("Error", "Please enter a valid extension!")
            return
        filtered_files = filter_files(extension)
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, f"Files with .{extension} extension:\n")
        self.output_text.insert(tk.END, "\n".join(filtered_files))

# Main
if __name__ == "__main__":
    root = tk.Tk()
    app = DownloadManagerApp(root)
    root.mainloop()
