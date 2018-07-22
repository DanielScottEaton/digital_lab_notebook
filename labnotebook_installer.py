import tkinter
import tkinter.filedialog
import os,sys
import platform
import shutil
class installer():
    def __init__(self,ostype):
        self.ostype = ostype
    def query(self):
        root = tkinter.Tk()
        self.targetpath = tkinter.filedialog.askdirectory(parent=root, initialdir='~', title='Please select a folder for your notebook.')
        root.destroy()
    def install(self):
        self.labnotebookpath = self.targetpath+"/Lab_Notebook/"
        os.mkdir(self.labnotebookpath)
        shutil.copyfile("./template.tex",self.labnotebookpath+"template.tex")
        with open("./labnotebook.py","r") as infile:
            template = infile.read().split("\n")
        template[-5] = '    notebookroot = "' + self.labnotebookpath + '"'
        outtxt = "\n".join(template)
        with open(self.labnotebookpath+"labnotebook.py","w") as outfile:
            outfile.write(outtxt)
        if self.ostype == "win":
            with open(self.labnotebookpath+"labnotebook.bat","w") as outfile:
                outfile.write("python labnotebook.py")
        else:
            with open(self.labnotebookpath+"labnotebook.sh","w") as outfile:
                outfile.write("python labnotebook.py")

if __name__ == '__main__':
    osstr = platform.platform()
    if "windows" in osstr.lower():
        print("Installing Windows Version.")
        install = installer("win")

    else:
        print("Installing Linux Verison.")
        install = installer("linux")
    install.query()
    install.install()