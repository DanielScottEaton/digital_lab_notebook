#requires imagemagick to run commands
import sys,os,io
import subprocess
from PIL import Image
from PyPDF2 import PdfFileWriter, PdfFileReader
from reportlab.pdfgen import canvas
from matplotlib.pyplot import imshow
from matplotlib import pyplot as plt
import cv2
import numpy as np
import tkinter 
import tkinter.filedialog
import tkinter.messagebox
import pickle as pkl
import shutil
from shutil import copyfile
import time
import os.path
class noteimport():

    """Imports pdfs from Sony DPT-RP1 and adds images. 
    
    This class provides a handle for importing a single multipage pdf of
    handwritten notes generated by the Sony DPT-RP1. It may be adapted to 
    other kinds of pdfs but will require some tuning of parameters. Primarily,
    this class scans through the input pdf for any rectangles and then prompts
    the user for a image file to insert at that box. This operation expands the
    filesize of the pdf, so for any pdfs where the box finding operation is not
    required, avoid using this class.
    
    Attributes:
        pages (list): Handles for raster versions of pages from imported pdf.
        pdf_file_reader_handles (list): Handles for pdf temporary files generated from images staged for insertion into the compiled document.
        pdfpath (str): Filepath to the note being compiled.
        projectpath (str): Filepath to the journal the note is being compiled into.
        pypdf_input (PdfFileReader object): PdfFileReader object containing the note being compiled.
        pypdf_input_filehandle (file): Handle for initial import of the note being compiled.
        pypdf_output (PdfFileWriter object): PdfFileWriter object for writing the compiled note.
    """

    def __init__(self,projectpath,pdfpath):
        """Initial
        
        Args:
            projectpath (str): Filepath to the journal the note is being compiled into.
            pdfpath (str): Filepath to the note being compiled.
        """
        self.projectpath = projectpath
        self.pdfpath = pdfpath
    def __rasterpages(self):
        self.pypdf_input_filehandle = open(self.pdfpath, "rb")
        self.pypdf_input = PdfFileReader(self.pypdf_input_filehandle)
        self.pypdf_output = PdfFileWriter()
        self.pages = []
        temp_folder_path = self.projectpath+"/tempsplit"
        os.mkdir(temp_folder_path)
        command = 'magick -density 72 -depth 8 -quality 85 "' + self.pdfpath + '" ' + temp_folder_path + '/page-%0d.png'
        process = subprocess.Popen(command, shell=True)
        process.wait()
        pagelist = os.listdir(temp_folder_path + "/")
        idxlist = np.array([int(item.split("-")[1][:-4]) for item in pagelist])
        sortlist = np.argsort(idxlist)
        sortedpages = np.array(pagelist)[sortlist].tolist()
        for item in sortedpages:
            pagepath = temp_folder_path + "/" + item    
            imgout = Image.open(pagepath,"r")
            imgout = imgout.convert('RGB')
            self.pages.append(imgout)
        shutil.rmtree(temp_folder_path)
    #taken from https://www.pyimagesearch.com/2016/02/08/opencv-shape-detection/
    def __isrectangle(self,contour):
        """Detects if a given conntour is a rectangle.
        
        Uses the Douglas-Peucker algorithm to determine the number of vertices
        in the input contour. Calls a rectangle if there are 4 vertices.
        
        Args:
            contour (contour object): A single contour object.
        
        Returns:
            bool: True if the contour is a rectangle.
        """
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
        if len(approx) == 4:
            return True
        else:
            return False
    def __previewrectangle(self,background,rect,xdim=700):
        """Queries the user for image placement.
        
        Displays a detected rectangle to the user and asks the user if they
        would like to place an image at that rectangle.
        
        Args:
            background (numpy array): Numpy array of the background image.
            rect (list): List of coordinates specifying a rectangle [x,y,w,h].
            xdim (int, optional): Width of the preview image. Default: 700
        
        Returns:
            bool: True if user wants to place an image.
        """
        a = xdim/background.size[0]
        resized = background.resize((int(background.size[0]*a),int(background.size[1]*a)))
        resized = np.array(resized)
        cv2.rectangle(resized,(int(rect[0]*a),int(rect[1]*a)),(int(rect[0]*a+rect[2]*a),int(rect[1]*a+rect[3]*a)),(0,255,0),2)
        cv2.imshow('Preview',resized)
        query = tkinter.Tk()
        result = tkinter.messagebox.askyesno(title='Prompt',message='Would you like to put an image here?')
        query.destroy()
        return result
    def __getrectangles(self,background,rectanglesize=100000):
        """Detects rectangles in an image.
        
        Detects all rectangles in the input image and records their coordinates
        as a list of [x,y,w,h] lists.
        
        Args:
            background (image object): PIL image object of the background image.
            rectanglesize (int, optional): Lower bound on the allowed internal area
            of detected rectangles. Default: 100000
        Returns:
            list: List of rectangle coordinates [x,y,w,h].
        """
        background = cv2.cvtColor(np.array(background),cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(background,100,255,1)[1]
        dilate = cv2.dilate(thresh,None,iterations=20)
        _,contours,hierarchy = cv2.findContours(dilate,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        rectangles = []
        for i,cnt in enumerate(contours):
            if hierarchy[0,i,3] == -1 and cv2.contourArea(cnt)>rectanglesize:
                if self.__isrectangle(cnt):
                    x,y,w,h = cv2.boundingRect(cnt)
                    rectangles.append([int(x),int(y),int(w),int(h)])
        return rectangles
    def __maprectangles(self,pageimage,pagenum,rectangles):
        """Places images in detected rectangles.
        
        Given an page image, a page number, and a list of detected rectangles, places images
        in each of these rectangles in the pdf. For each rectangle, will query the 
        user for confirmation and a image filepath.
        
        Args:
            pageimage (numpy array): Numpy array of the page image.
            pagenum (int): Current page number.
            rectangles (list): List of rectangle coordinates [x,y,w,h].
        """
        current_page = self.pypdf_input.getPage(pagenum)
        root = tkinter.Tk()
        for j,rect in enumerate(rectangles):
            usercheck = self.__previewrectangle(pageimage,rect)
            if usercheck:
                targetpath = tkinter.filedialog.askopenfilename(parent=root, initialdir='~', title='Please select a file.')
                targetim = Image.open(targetpath,"r")
                targetim = targetim.convert('RGB')
                targetim = targetim.resize((rect[2],rect[3]))
                targetim.save(self.projectpath + "tempresized.png")
                with open(self.projectpath + "tempimgs/imgpdf_"+str(pagenum)+"_"+str(j)+".pdf","wb") as outfile:
                    imgpdf = canvas.Canvas(outfile)
                    imgpdf.drawImage(self.projectpath + "/tempresized.png",rect[0],792 - rect[1] - rect[3])
                    imgpdf.save()
                self.pdf_file_reader_handles.append(open(self.projectpath + "tempimgs/imgpdf_"+str(pagenum)+"_"+str(j)+".pdf","rb"))
                openimgpdf = PdfFileReader(self.pdf_file_reader_handles[-1])
                current_page.mergePage(openimgpdf.getPage(0))
                os.remove(self.projectpath + "tempresized.png")
            cv2.destroyAllWindows()
        root.destroy()
        self.pypdf_output.addPage(current_page)
    def compile(self,filepath,archivepath,images=True):
        """Compiles output pdf, optionally scanning the input pdf for rectangles
        to place images into. This option is intended to be enabled when
        compiling from hadwritten notes.
        
        Args:
            filepath (str): Filepath to write output pdf to.
            archivepath (str): Filepath to write archived output pdf to.
            images (bool, optional): Option enables image insertion into drawn 
            rectangles when True
        """
        if os.path.isfile(archivepath):
            sys.exit("File of the same name already exists in the archive!!!")
        else:
            copyfile(self.pdfpath,archivepath)
        if images:
            self.pdf_file_reader_handles = []
            self.__rasterpages()
            os.mkdir(self.projectpath + "tempimgs")
            for i,page in enumerate(self.pages):
                rectangles = self.__getrectangles(page)
                self.__maprectangles(page,i,rectangles)
            with open(filepath, "wb") as outfile:
                self.pypdf_output.write(outfile)
            self.pypdf_input_filehandle.close()
            for item in self.pdf_file_reader_handles:
                item.close()
            shutil.rmtree(self.projectpath + "tempimgs")
        else:
            copyfile(self.pdfpath,filepath)
class latexdoc():

    """Class for manipulating lab notebook project folders and compiling into latex master documents.
    
    This class provides a handle for managing lab notebook project folders. Possesses
    functions for creating new project folders and updating old ones. Subfunctions
    for compiling new notes, metadata and writing master latex files are included.
    Intended for compiling standard pdf files as well as handwritten notes generated
    by the Sony DPT-RP1. Generates master pdfs with all compiled documents, table of
    contents, and an index, sorted by date.
    
    Attributes:
        notebookpath (str): Filepath of master notebook folder containing all journals.
        notesourcepath (str): Filepath of note folder containing notes staged for compiling with
        rectangle detection. Intended for handwritten notes needing image insertion.
        notespath (str): Filepath of note archive containing all notes that have already been compiled.
        Filenames in this folder are ordered by date.
        projectpath (str): Filepath of target journal folder. 
        template (list): List of strings corresponding to lines of template .tex document which
        specifies the standard format of the output latex document.
        texdict (dict): Dictionary containing the title and page metadata of the target journal.
        Saved as notebook.pkl pickle file in the target journal directory folder.
        textsourcepath (str): Filepath of note folder containing notes staged for compiling without
        rectangle detection.
        title (str): Title of target journal. Same as the journal foldername.
    """

    def __init__(self,notebookpath):
        """Summary
        
        Args:
            notebookpath (TYPE): Description
        """
        self.notebookpath = notebookpath
    def loadproject(self,title):
        """Summary
        
        Args:
            title (TYPE): Description
        """
        self.title = title
        self.projectpath = self.notebookpath+title+"/"
        self.notesourcepath = self.projectpath+"New_Imagenotes/"
        self.textsourcepath = self.projectpath+"New_Notes/"
        self.notespath = self.projectpath+"Notes/"
        self.archivepath = self.projectpath+"Archive/"
        with open((self.projectpath+"notebook.pkl"),"rb") as infile:
            self.texdict = pkl.load(infile)
    def newproject(self,title):
        """Summary
        
        Args:
            title (TYPE): Description
        """
        self.title = title
        self.projectpath = self.notebookpath+title+"/"
        self.notesourcepath = self.projectpath+"New_Imagenotes/"
        self.textsourcepath = self.projectpath+"New_Notes/"
        self.notespath = self.projectpath+"Notes/"
        self.archivepath = self.projectpath+"Archive/"
        self.texdict = {"title":title,"notes":[]}
        shutil.rmtree(self.projectpath)
        os.mkdir(self.projectpath)
        os.mkdir(self.notesourcepath)
        os.mkdir(self.textsourcepath)
        os.mkdir(self.notespath)
        os.mkdir(self.archivepath)
        with open((self.projectpath+"notebook.pkl"),"wb") as outfile:
            pkl.dump(self.texdict,outfile)
    def updatetitle(self):
        """Summary
        """
        self.texdict["title"] = self.title
        with open((self.projectpath+"notebook.pkl"),"wb") as outfile:
            pkl.dump(self.texdict,outfile)
    def __checkpages(self,pdfpath):
        """Summary
        
        Args:
            pdfpath (TYPE): Description
        
        Returns:
            TYPE: Description
        """
        command = "pdfinfo " + pdfpath + " | grep -a Pages: "
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        process.wait()
        line = process.stdout.readline()
        pagenum = int(line.decode('utf-8').split()[1])
        return pagenum
    def addnote(self,newentry,notetitle,keywordlist,date,remove=False,images=False): #for handwritten things
        """Summary
        
        Args:
            newentry (TYPE): Description
            notetitle (TYPE): Description
            keywordlist (TYPE): Description
            date (TYPE): Description
            remove (bool, optional): Description
            images (bool, optional): Description
        """
        pagenum = len(self.texdict["notes"])
        notename = "note_" + str(pagenum) + ".pdf"
        if images:
            workingnote = noteimport(self.projectpath,self.notesourcepath+newentry)
        else:
            workingnote = noteimport(self.projectpath,self.textsourcepath+newentry)
        workingnote.compile(self.notespath+notename,self.archivepath+newentry,images=images)
        del workingnote
        ttlpages = self.__checkpages(self.notespath+notename)
        self.texdict["notes"].append({"notetitle":notetitle,"keywords":keywordlist,"date":date,"pages":ttlpages})
        self.__sortbydate()
        with open((self.projectpath+"notebook.pkl"),"wb") as outfile:
            pkl.dump(self.texdict,outfile)
        if remove:
            if images:
                os.remove(self.notesourcepath+newentry)
            else:
                os.remove(self.textsourcepath+newentry)
    def __sortbydate(self):
        """Summary
        """
        datearr = np.array([np.array(item["date"].split("/")) for item in self.texdict["notes"]]).T
        if len(datearr) < 1:
            return
        ind = np.lexsort((datearr[1],datearr[0],datearr[2]))
        for tgt,cur in enumerate(ind):
            currentname = "note_" + str(cur) + ".pdf"
            targetname = "snote_" + str(tgt) + ".pdf"
            os.rename(self.notespath+currentname,self.notespath+targetname)
        for i in range(len(ind)):
            currentname = "snote_" + str(i) + ".pdf"
            targetname = "note_" + str(i) + ".pdf"
            os.rename(self.notespath+currentname,self.notespath+targetname)
        self.texdict["notes"] = (np.array(self.texdict["notes"])[ind]).tolist()    
    def removenotes(self):
        """Summary
        """
        archive_note_indices = os.listdir(self.notespath)
        noteinds = [int(note.split("_")[1][:-4]) for note in archive_note_indices]
        noteinds.sort()
        self.texdict["notes"] = [item for i,item in enumerate(self.texdict["notes"]) if i in noteinds]
        for i in range(len(noteinds)):
            current_ind = noteinds[i]
            currentname = "note_" + str(current_ind) + ".pdf"
            targetname = "note_" + str(i) + ".pdf"
            os.rename(self.notespath+currentname,self.notespath+targetname)
        self.__sortbydate()
        with open((self.projectpath+"notebook.pkl"),"wb") as outfile:
            pkl.dump(self.texdict,outfile)
    def __latexpage(self,noteidx):
        """Summary
        
        Args:
            noteidx (TYPE): Description
        
        Returns:
            TYPE: Description
        """
        header = [self.template[26]] + ["\invisiblesection{"+\
        self.texdict["notes"][noteidx]["notetitle"]+"}"] + self.template[28:34]
        body = [" "*20 + "Note: " + self.texdict["notes"][noteidx]["notetitle"] +\
        " " + str(noteidx) + "\\\\"," "*20 + "Date: " + \
        str(self.texdict["notes"][noteidx]["date"]) + "\\\\",\
        " "*20 + "Keywords: " + " ".join(["\\index{" + item.lower() + "}" + item for item in self.texdict["notes"][noteidx]["keywords"]])]
        notepath = self.notespath + "note_" + str(noteidx) + ".pdf"
        closer = self.template[37:41] + ["}]{"+notepath+"}"]
        if self.texdict["notes"][noteidx]["pages"]>1:
            closer += ["\\includepdf[pages=2-]{"+notepath+"}"]
        full =  header+body+closer
        return full
    def __errormsg(self,message):
        """Summary
        
        Args:
            message (TYPE): Description
        """
        root = tkinter.Tk()
        tkinter.Label(root, text=message).grid(row=0)
        tkinter.Button(root, text='Done', command=root.quit).grid(row=3, column=0, sticky=tkinter.W, pady=4)
        root.mainloop()
        root.destroy()
    def __checkcorruption(self):
        """Summary
        """
        with open((self.projectpath+"notebook.pkl"),"rb") as infile:
            self.texdict = pkl.load(infile)
        dictlen = len(self.texdict["notes"])
        noteslen = len(os.listdir(self.notespath))
        if dictlen != noteslen:
            self.__errormsg("Error: Note number mismatched.")
    def compilelatex(self):
        """Summary
        """
        self.__checkcorruption()
        with open((self.notebookpath+"template.tex"),"r") as infile:
            self.template = infile.read().split("\n")
        textitle = ""
        for item in self.texdict["title"]:
            if item == "_":
                textitle+=" "
            else:
                textitle+=item
        texlist = self.template[:20] + \
        ["\\title{"+textitle+"}"] + \
        self.template[21:26]
        for i in range(len(self.texdict["notes"])):
            texlist += self.__latexpage(i)
        texlist += self.template[43:45]
        del self.template
        outtex = "\n".join(texlist)
        with open((self.projectpath+"notebook.tex"),"w") as outfile:
            outfile.write(outtex)
    def writepdf(self):
        """Summary
        """
        command = "pdflatex -aux-directory=" + \
        self.projectpath + "notebook_aux " + \
        "-output-directory=" + \
        self.projectpath[:-1] + " " + \
        self.projectpath + "notebook.tex"
        result = subprocess.call(command,shell=False)
    def makeindex(self):
        """Summary
        """
        command = 'makeindex "' + self.projectpath + \
        'notebook_aux/notebook.idx"'
        result = subprocess.call(command,shell=False)
class updateloop():
    """Summary
    
    Attributes:
        notebookpath (TYPE): Description
    """
    def __init__(self,notebookpath):
        """Summary
        
        Args:
            notebookpath (TYPE): Description
        """
        self.notebookpath = notebookpath
    def __keyworddatequery(self):
        """Summary
        
        Returns:
            TYPE: Description
        """
        root = tkinter.Tk()
        tkinter.Label(root, text="Note Title").grid(row=0)
        tkinter.Label(root, text="Keywords (space delimited)").grid(row=1)
        tkinter.Label(root, text="Date (mm/dd/yyyy)").grid(row=2)
        notetitle = tkinter.Entry(root)
        keywords = tkinter.Entry(root)
        date = tkinter.Entry(root)
        notetitle.grid(row=0, column=1)
        keywords.grid(row=1, column=1)
        date.grid(row=2, column=1)
        tkinter.Button(root, text='Done', command=root.quit).grid(row=4, column=0, sticky=tkinter.W, pady=5)
        root.mainloop()
        notetitle = notetitle.get()
        keywords = keywords.get()
        date = date.get()
        root.destroy()
        keywords = keywords.split(" ")
        return notetitle,keywords,date
    def __checknewnotes(self,title):
        """Summary
        
        Args:
            title (TYPE): Description
        """
        dochandle = latexdoc(self.notebookpath)
        dochandle.loadproject(title)
        titlepath = self.notebookpath+title+"/"
        for item in os.listdir(titlepath+"New_Imagenotes/"):
            newitem=True
            notetitle,keywords,date = self.__keyworddatequery()
            dochandle.addnote(item,notetitle,keywords,date,remove=True,images=True)
        for item in os.listdir(titlepath+"New_Notes/"):
            newitem=True
            notetitle,keywords,date = self.__keyworddatequery()
            dochandle.addnote(item,notetitle,keywords,date,remove=True,images=False)
        del dochandle
    def __checkmissing(self,title):
        """Summary
        
        Args:
            title (TYPE): Description
        
        Returns:
            TYPE: Description
        """
        dochandle = latexdoc(self.notebookpath)
        dochandle.loadproject(title)
        if len(os.listdir(dochandle.notespath)) != len(dochandle.texdict["notes"]):
            dochandle.removenotes()
            return True
        else:
            return False
    def __compileall(self,title):
        """Summary
        
        Args:
            title (TYPE): Description
        """
        dochandle = latexdoc(self.notebookpath)
        dochandle.loadproject(title)
        dochandle.compilelatex()
        dochandle.writepdf()
        dochandle.makeindex()
        dochandle.writepdf()
    def __newproject(self,title):
        """Summary
        
        Args:
            title (TYPE): Description
        """
        dochandle = latexdoc(self.notebookpath)
        dochandle.newproject(title)
    def __updatetitle(self,title):
        """Summary
        
        Args:
            title (TYPE): Description
        """
        dochandle = latexdoc(self.notebookpath)
        dochandle.loadproject(title)
        if dochandle.texdict["title"] != title:
            dochandle.updatetitle()
    def update(self):
        """Summary
        """
        for title in os.listdir(self.notebookpath):
            compilenotes=False
            titlepath = self.notebookpath+title+"/"
            if not os.path.isdir(titlepath):
                continue
            if "notebook.pkl" not in os.listdir(titlepath):
                self.__newproject(title)
            self.__updatetitle(title)
            numnew = len(os.listdir(titlepath+"New_Imagenotes/")) + \
            len(os.listdir(titlepath+"New_Notes/"))
            if numnew>0:
                self.__checknewnotes(title)
                compilenotes=True
            missing = self.__checkmissing(title)
            if missing:
                compilenotes=True
            if compilenotes:
                self.__compileall(title)

if __name__ == '__main__':
    notebookroot = "./"
    uploop = updateloop(notebookroot)
    while True:
        time.sleep(1.)
        uploop.update()