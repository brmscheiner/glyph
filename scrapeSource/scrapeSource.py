import reader
import converter
import os
import writer

def genGraphData(project_path):
    ASTs        = reader.fetch(project_path)
    fdefs,calls = converter.convert(ASTs,project_path)
    writer.jsonGraph(fdefs,calls)

if __name__=="__main__":
    project_path = os.path.join(
                                'C:\\','Users','scheinerbock','Desktop',
                                'ideogram','scrapeSource','test','bpl-compyler-master'
                                )
    genGraphData(project_path)