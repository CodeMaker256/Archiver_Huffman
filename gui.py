import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as fd
import tkinter.messagebox as msgbox

import huffman_coding as hf

TITLE = "Архиватор"
ROOT_W = 600
ROOT_H = 400

# Убираем размытость виджетов tkinter в Windows 10:
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass


def formatFileName(filename: str, length=63) -> str:
    """
    :param filename: путь к файлу
    :param length: длина, до которой нужно обрезать имя пути
    :return: сокращенное посередине имя пути для отображения на экране
    """
    if len(filename) <= length:
        return filename
    return filename[:(length - 3) // 2] + "..." + filename[-(length - 3) // 2:]


def formatSize(x: int) -> str:
    e = ("Байт", "Кб", "Мб", "Гб")
    k = 0
    while not 0.5 < x < 512 and k < 3:
        k += 1
        x /= 1024
    x = round(x, 1)
    return str(x) + " " + e[k]


class TopWindow(tk.Toplevel):
    """
    Виджет окна, находящегося выше по уровню
    """

    def __init__(self, title, width, height):
        super().__init__()
        self.title(title)
        self.geometry(f"{width}x{height}+{(SCREEN_W - width) // 2}+{(SCREEN_H - height) // 2}")
        self.protocol("WM_DELETE_WINDOW", self.dismiss)
        self.grab_set()

    def dismiss(self):
        self.grab_release()
        self.destroy()


class windowProgress(TopWindow):
    """
    Виджет окна, отвечающего за процесс обработки файлов.
    filenames: список имен обрабатываемых файлов
    mode: режим обработки ("to", "from", "preview")
    statisticData: статистика для файлов
    interrupt_flag: флаг прерывания обработки файлов
    """

    def __init__(self, filenames: tuple, mode: str):
        assert mode in ("to", "from", "preview")

        self.filenames = filenames
        self.mode = mode
        self.statisticData = None
        self.interrupt_flag = False

        if mode == "to":
            title = "Добавление в архив"
        elif mode == "from":
            title = "Извлечение из архива"
        elif mode == "preview":
            title = "Расчет"

        super().__init__(title=title, width=500, height=100)
        self.protocol("WM_DELETE_WINDOW", self.interrupt)

        self.lblCurrentFileName = tk.Label(self,
                                           text=formatFileName(self.filenames[0][0] if mode != "preview" else
                                                               self.filenames[0]))
        self.percentCounter = tk.IntVar(value=0)
        self.progressBarPercents = ttk.Progressbar(self,
                                                   orient="horizontal",
                                                   maximum=100,
                                                   variable=self.percentCounter)
        self.filesCounter = tk.IntVar(value=0)
        self.progressBarFiles = ttk.Progressbar(self,
                                                orient="horizontal",
                                                maximum=len(filenames),
                                                variable=self.filesCounter)
        self.lblCurrentFileName.pack(expand=0, fill=tk.X)
        self.progressBarPercents.pack(expand=0, fill=tk.X)
        self.progressBarFiles.pack(expand=0, fill=tk.X)

        self.update()

        if mode == "to":
            self.cmnd_toArchiveMany()
        elif mode == "from":
            self.cmnd_fromArchiveMany()
        elif mode == "preview":
            self.statisticData = self.cmnd_preview()

        self.dismiss()

    def cmnd_toArchiveMany(self):
        """
        Запускает создание архивов.
        """
        errLst = hf.toArchiveMany(filenames=self.filenames, funcAfterFile=self.funcAfterFile,
                                  funcAfterPercent=self.funcAfterPercent)
        if self.interrupt_flag:
            msgbox.showerror(message="Преобразование могло завершиться с ошибками")
            return

        if not errLst:
            msgbox.showinfo(title="Преобразование завершено",
                            message=f"Для всех файлов ({len(self.filenames)} шт.) успешно созданы архивы")
        else:
            symb = "\n"
            msgbox.showerror(title="Преобразование завершено",
                             message=f"Для некоторых файлов ({len(errLst)} / {len(self.filenames)} шт.) не удалось "
                                     f"создать архивы:\n{symb.join(errLst)}")

    def cmnd_fromArchiveMany(self):
        """
        Запускает извлечение файлов из архивов.
        """
        errLst = hf.fromArchiveMany(filenames=self.filenames, funcAfterFile=self.funcAfterFile,
                                    funcAfterPercent=self.funcAfterPercent)

        if self.interrupt_flag:
            msgbox.showerror(message="Преобразование могло завершиться с ошибками")
            return

        if not errLst:
            msgbox.showinfo(title="Преобразование завершено",
                            message=f"Все файлы ({len(self.filenames)} шт.) удалось успешно извлечь из архивов")
        else:
            symb = "\n"
            msgbox.showerror(title="Преобразование завершено",
                             message=f"Некоторые архивы ({len(errLst)} / {len(self.filenames)} шт.) не удалось "
                                     f"восстановить:\n{symb.join(errLst)}")

    def cmnd_preview(self):
        """
        Запускает расчет статистики для файлов без созданияя архивов.
        """
        return hf.preview(filenames=self.filenames, funcAfterPercent=self.funcAfterPercent, funcAfterFile=self.funcAfterFile)

    def funcAfterFile(self):
        """
        Для вызова после обработки очередного файла, двигает значение ProgressBar.
        """
        self.filesCounter.set(self.filesCounter.get() + 1)
        self.percentCounter.set(0)
        try:
            if self.mode != "preview":
                self.lblCurrentFileName["text"] = self.filenames[self.filesCounter.get()][0]
            else:
                self.lblCurrentFileName["text"] = self.filenames[self.filesCounter.get()]
        except IndexError:
            pass
        self.update()

    def funcAfterPercent(self):
        """
        Для вызова после обработки каждого 1% файла, двигает значение ProgressBar.
        """
        self.percentCounter.set(self.percentCounter.get() + 1)
        self.update()

    def getStatisticData(self):
        return self.statisticData

    def interrupt(self):
        if self.mode == "preview" or \
                msgbox.askokcancel(message="В результате этого действия некоторые из создаваемых "
                                           "файлов могут оказаться повреждены"):
            self.interrupt_flag = True
            hf.RUN = False


class windowChooseToArchive(TopWindow):
    """
    Виджет окна, отвечающего за процесс выбора файлов для добавления в архив.
    """

    def __init__(self):
        self.filenames = fd.askopenfilenames(title="Выберите файлы для создания архивов")
        if self.filenames:
            # Проверка на наличие пустых файлов:
            nullSizeLst = self.checkSizeFiles()
            if nullSizeLst:
                msgbox.showerror(
                    message="Нельзя создать архивы для файлов нулевого размера:\n{}\n"
                            "Выберите только непустые файлы".format("\n".join(nullSizeLst)))
                return

            super().__init__("Добавить в архив...", 1200, ROOT_H)
            self.frameMenu = tk.Frame(self)
            self.btnPreview = tk.Button(self.frameMenu,
                                        text="Предпросмотр",
                                        command=self.click_btnPreview)
            self.btnToArchive = tk.Button(self.frameMenu,
                                          text="Архивировать",
                                          command=self.click_btnToArchive)
            self.btnPreview.pack(side=tk.LEFT, expand=1, fill=tk.X)
            self.btnToArchive.pack(side=tk.LEFT, expand=1, fill=tk.X)
            self.frameMenu.pack(fill=tk.X)

    def click_btnPreview(self):
        """
        Запускает процесс расчета размеров архивов, открывая окно windowProgress, и строит соответствующую таблицу.
        """
        self.btnPreview["state"] = "disabled"
        statisticData = windowProgress(filenames=self.filenames, mode="preview").getStatisticData()

        # Построение таблицы:
        columns = ("filename", "oldSize", "newSize", "compression")
        table = ttk.Treeview(self,
                             columns=columns,
                             show="headings")
        table.pack(fill=tk.BOTH, expand=1)

        table.heading(column="filename", text="Файл")
        table.heading(column="oldSize", text="Размер файла, байт")
        table.heading(column="newSize", text="Размер архива, байт")
        table.heading(column="compression", text="Сжатие, %")

        width = self.winfo_width()
        table.column("#1", width=int(0.55 * width))
        table.column("#2", width=int(0.15 * width))
        table.column("#3", width=int(0.15 * width))
        table.column("#4", width=int(0.15 * width))

        for oneData in statisticData:
            table.insert("", tk.END, values=oneData)

    def click_btnToArchive(self):
        """
        Запускает процесс добавления файлов в архив, открывая окно windowProgress.
        """
        saveDir = fd.askdirectory(title="Выберите папку для сохранения архивов...")
        if saveDir:
            self.filenames = [[oldName, saveDir + "/" + os.path.splitext(os.path.basename(oldName))[0]] for
                              oldName in self.filenames]

            # Исправление одинаковых имен для сохраняемых файлов:
            for i in range(len(self.filenames) - 1):
                counter = 1
                for j in range(i + 1, len(self.filenames)):
                    if self.filenames[i][1] == self.filenames[j][1]:
                        self.filenames[j][1] += f" ({counter})"
                        counter += 1

            self.dismiss()
            windowProgress(filenames=tuple(self.filenames), mode="to")

    def checkSizeFiles(self) -> list:
        """
        :return: список имен файлов, имеющих нулевой размер
        """
        nullSizeLst = []
        for filename in self.filenames:
            if os.path.getsize(filename) == 0:
                nullSizeLst.append(filename)
        return nullSizeLst


class windowChooseFromArchive(TopWindow):
    """
    Виджет окна, отвечающего за процесс выбора файлов для извлечения из архива.
    """

    def __init__(self):
        self.filenames = fd.askopenfilenames(title="Выберите архивы для извлечения...",
                                             filetypes=[("", "." + hf.EXTENSION)])
        if self.filenames:
            saveDir = fd.askdirectory(title="Выберите папку для сохранения извлеченных файлов...")
            if saveDir:
                super().__init__("Извлечение из архива...", ROOT_W, ROOT_H)
                self.filenames = [(oldName, saveDir + "/" + os.path.splitext(os.path.basename(oldName))[0]) for
                                  oldName in self.filenames]
                self.dismiss()
                windowProgress(filenames=tuple(self.filenames), mode="from")


class windowMain(tk.Tk):
    """
    Виджет главного окна.
    """

    def __init__(self):
        global SCREEN_W, SCREEN_H

        super().__init__()

        SCREEN_W = self.winfo_screenwidth()
        SCREEN_H = self.winfo_screenheight()

        self.title(TITLE)
        self.frameMenu = tk.Frame(self)
        self.geometry(f"{ROOT_W}x{ROOT_H}+{(SCREEN_W - ROOT_W) // 2}+{(SCREEN_H - ROOT_H) // 2}")
        self.btnChooseToArchive = tk.Button(self.frameMenu,
                                            text="Добавить в архив...",
                                            command=self.click_btnChoseToArchive)
        self.btnChooseFromArchive = tk.Button(self.frameMenu,
                                              text="Извлечь из архива...",
                                              command=self.click_btnChoseFromArchive)
        self.btnChooseToArchive.pack(side=tk.LEFT, expand=1, fill=tk.X)
        self.btnChooseFromArchive.pack(side=tk.LEFT, expand=1, fill=tk.X)
        self.frameMenu.pack(fill=tk.X)

        self.mainloop()

    def click_btnChoseToArchive(self):
        windowChooseToArchive()

    def click_btnChoseFromArchive(self):
        windowChooseFromArchive()
