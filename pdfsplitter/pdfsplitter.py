from PyPDF2 import PdfReader, PdfWriter
import sys

def split(original: PdfReader, instructions, outputNames=[]):
    # Split the instructions into a list of pages
    pages_instructions = instructions.split(',')
    pdf_writer = PdfWriter()
    
    for index, instr in enumerate(pages_instructions):
        frtosets = instr.split('+')
        for frtoset in frtosets:
            fr, to = frtoset.split('-')
            
            # Extract the pages from the original PDF
            for page_num in range(int(fr)-1, int(to)):
                pdf_writer.add_page(original.pages[page_num])
            
        # Write the new PDF to a file
        out_name = (outputNames[index] if len(outputNames) > index else 'output' + str(index)) + '.pdf'
        with open(out_name, 'wb') as output_pdf:
            pdf_writer.write(output_pdf)
            pdf_writer = PdfWriter()
    
def process_args():
    input_file = sys.argv[1]
    instructions = sys.argv[2]
    output_files = sys.argv[3].split(',') if len(sys.argv) > 3 else 'output.pdf'
    return input_file, instructions, output_files

if __name__ == '__main__':
    # get params from sys args
    input_file, instructions, output_files = process_args()
    # Open the PDF
    pdf = PdfReader(input_file)
    split(pdf, instructions, output_files)
        

