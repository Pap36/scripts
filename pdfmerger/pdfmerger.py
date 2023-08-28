from tkinter.filedialog import askopenfilenames, asksaveasfilename
from pypdf import PdfMerger
import os

# create a function which checks if a file exists at the given path
def file_exists(path):
    try:
        with open(path, 'r') as _:
            return True
    except FileNotFoundError as _:
        return False

# create a function to let the user select the pdfs to merge
def pdfs_to_merge():
    pdfs = []
    # open the file explorer and let the user select a pdf
    pdfs = askopenfilenames(filetypes=[('PDF Files', '*.pdf')])
    # return a list of paths of the pdfs
    return pdfs
        
# create a function which merges the PDFs
def merge_pdfs(pdfs):
    merger = PdfMerger()
    for pdf in pdfs:
        merger.append(pdf)

    # open the explorer and ask the user to select a folder and a name for the merged PDF
    path = asksaveasfilename(filetypes=[('PDF Files', '*.pdf')])
    if path == '':
        merger.close()
        return
    merger.write(path)
    merger.close()    

# create a function which opens the merged PDF
def open_merged_pdf():
    os.startfile('merged.pdf')

if __name__ == '__main__':
    pdfs = pdfs_to_merge()
    merge_pdfs(pdfs)