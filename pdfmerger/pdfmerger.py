from tkinter.filedialog import askopenfilenames, asksaveasfilename
from pypdf import PdfMerger

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
    path = asksaveasfilename(filetypes=[('PDF Files', '*.pdf')],initialfile='merged.pdf')
    try:
        merger.write(path)
        merger.close()    
    except:
        merger.close()

if __name__ == '__main__':
    pdfs = pdfs_to_merge()
    if len(pdfs) == 0:
        exit()
    merge_pdfs(pdfs)