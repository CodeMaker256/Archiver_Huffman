import os
from math import ceil

import path_tools as pt

EXTENSION = "huff_archive"

RUN = True


class Freq:
    """
    Содержит частоты каждого байта, встречающегося в определенном файле
    freq: {byte: count, ...}
    """
    def __init__(self, filename: str, funcAfterPercent=None):
        self.freq = {}

        oldFileSize = os.path.getsize(filename)

        chunk_counter = 0
        with open(filename, "rb") as file:
            chunk = file.read(1)
            while chunk:
                if not RUN:
                    return
                try:
                    self.freq[ord(chunk)] += 1
                except KeyError:
                    self.freq[ord(chunk)] = 1
                chunk_counter += 1
                if funcAfterPercent and int(chunk_counter / oldFileSize * 100) - int(
                        (chunk_counter - 1) / oldFileSize * 100) == 1:
                    funcAfterPercent()
                chunk = file.read(1)

        # Добавляем еще один байт с нулевой частотой, если файл состоит из одинаковых байтов, для того,
        # чтобы можно было построить дерево
        if len(self.freq) == 1:
            self.freq[([k for k in self.freq.keys()][0] + 1) % 256] = 0

    def toList(self):
        """
        Возвращает атрибут self.freq в виде списка
        """
        return [[k, v] for k, v in self.freq.items()]


class HuffTree:
    """
    Строит дерево Хаффмана в виде списка вершин.
    filename: "filename"
    freq: Freq(filename)
    tree: [leafs: (byte, selfId), ..., edges: (toIdif0, toIdif1), ..., root: (toIdif0, toIdif1)]
    codes: {byte: "bincode", ...}
    """

    def __init__(self, filename: str, from_: str, funcAfterPercent=None):
        assert from_ in ("file", "archive")

        self.filename = filename
        self.freq = None
        self.tree = None
        self.codes = None

        if from_ == "file":
            self.initFromFile(funcAfterPercent)
        elif from_ == "archive":
            self.initFromArchive()

    def initFromFile(self, funcAfterPercent=None):
        """
        Возвращает объект HuffTree для исходного файла.
        """

        def insertTopToFreq(freqLst: list, newTop: list[int, list[int, int], int]) -> None:
            """
            Вставляет newTop в отсортированный по невозрастанию freqLst с помощью бинпоиска.
            """
            if len(freqLst) == 0:
                freqLst.append(newTop)
                return
            if freqLst[0][2] <= newTop[2]:
                freqLst.insert(0, newTop)
                return
            if freqLst[-1][2] >= newTop[2]:
                freqLst.append(newTop)
                return
            a = 0
            b = len(freqLst) - 1
            while a <= b:
                k = (a + b) // 2
                if freqLst[k - 1][2] >= newTop[2] > freqLst[k][2]:
                    freqLst.insert(k, newTop)
                    break
                if freqLst[k][2] >= newTop[2]:
                    a = k + 1
                else:
                    b = k - 1

        self.freq = Freq(filename=self.filename, funcAfterPercent=funcAfterPercent)
        freqLst = self.freq.toList()
        # now freqLst: [[byte, count], ...]
        freqLst.sort(key=lambda x: x[1], reverse=True)
        for topID in range(len(freqLst)):
            freqLst[topID].insert(0, topID)
        # now freqLst: [[topID, byte, count], ...]
        self.tree = [(top[1], top[0]) for top in freqLst]
        while len(freqLst) > 1:
            # Проверка правильной сортировки: assert str(freqLst) == str(sorted(freqLst, key=lambda x: x[2], reverse=True))
            # newTop: [topID, (toTopID0, toTopID1), sumOfCount]
            newTop = [len(self.tree), (freqLst[-2][0], freqLst[-1][0]), freqLst[-2][2] + freqLst[-1][2]]
            freqLst.pop()
            freqLst.pop()
            insertTopToFreq(freqLst, newTop)
            self.tree.append(newTop[1])

    def initFromArchive(self):
        """
        Возвращает объект HuffTree, данные для которого записаны в архиве.
        self.freq при этом == None
        """
        with open(self.filename, "rb") as file:
            # Пропускаем данные об расширение исходного файла
            extLen = ord(file.read(1))
            file.read(extLen)

            # Восстанавливаем дерево
            self.tree = []
            treesize = ord(file.read(1)) * 256 + ord(file.read(1))
            for i in range(treesize):
                self.tree.append(
                    (ord(file.read(1)) * 256 + ord(file.read(1)), ord(file.read(1)) * 256 + ord(file.read(1))))

    def len(self) -> int:
        """
        :return: количество вершин в дереве
        """
        return len(self.tree)

    def lenInArchive(self) -> int:
        """
        :return: длина данных о дереве в байтах, которые сохраняются в архив
        """
        return len(self.tree) * 4 + 2

    def lenArchiveData(self) -> int:
        """
        :return: длина архивированных данных (без доп.) в байтах с помощью данного дерева на основе списка частот
        """
        codes = self.getCodes()
        return ceil(sum(len(codes[byte]) * count for byte, count in self.getFreq().toList()) / 8)

    def tops(self) -> list[(int, int), ...]:
        """
        :return: список вершин дерева
        """
        return self.tree

    def isLeaf(self, topID: int) -> bool:
        """
        :param topID: номер вершины
        :return: True, если вершина является листом дерева, иначе False
        """
        return self.tree[topID][1] == topID

    def getRootID(self) -> int:
        """
        :return: номер вершины, являющейся корнем дерева
        """
        return len(self.tree) - 1

    def getNextTopID(self, topID: int, bit: int) -> int:
        """
        :param topID: номер текущей вершины
        :param bit: номер ветки
        :return: номер вершины ниже по уровню, соединенной с текущей вершиной веткой bit
        """
        assert bit in (0, 1)
        return self.tree[topID][bit]

    def getByte(self, topID: int) -> int:
        """
        :param topID: номер вершины-листа
        :return: байт, код для которого заканчивается в вершине topID
        """
        assert self.isLeaf(topID)
        return self.tree[topID][0]

    def getFreq(self) -> Freq:
        """
        :return: объект, содержащий список частот, по которому построено данное дерево
        """
        return self.freq

    def getCodes(self) -> dict:
        """
        :return: двоичные коды для каждого байта в формате {byte: "code", ...}
        """

        def deepSearch(topID: int, code: str, tree: HuffTree, codes: dict) -> None:
            """
            Строит двоичные коды для каждого байта на основе tree и сохраняет их в dictftion
            """
            if tree.isLeaf(topID):
                codes[tree.getByte(topID)] = code
                return
            deepSearch(tree.getNextTopID(topID, 0), code + "0", tree, codes)
            deepSearch(tree.getNextTopID(topID, 1), code + "1", tree, codes)

        if self.codes:
            return self.codes
        codes = {}
        deepSearch(self.getRootID(), "", self, codes)
        self.codes = codes
        return self.codes

    def toBytes(self) -> bytes:
        """
        :return: данные о дереве для сохранения в файл-архив
                 (2 байта на размер дерева и по 4 байта на каждую вершину (по 2 байта на число из пары))
        """
        assert self.len() <= 2 ** 16 - 1
        lst = [self.len() // 256, self.len() % 256]
        for top in self.tops():
            assert top[0] <= 2 ** 16 - 1 and top[1] <= 2 ** 16 - 1
            lst += [top[0] // 256, top[0] % 256, top[1] // 256, top[1] % 256]
        return bytes(lst)


def toArchive(oldName: str, newName: str, funcAfterPercent=None) -> tuple:
    """
    Создает архив на основе исходного файла.
    Структура архива:
        размер исх. расширения: 1 байт
        исх. расширение: 1 байт - 1 символ
        данные о дереве: 2 + 4 * [длина дерева] байт
        размер исходного файла (1 байт == число-цифра) + 1 байт byte10
        массив байтов
    :param oldName: путь к исходному файлу
    :param newName: путь к архиву, без расширения
    :param funcAfterPercent: вызывается каждый раз после обработки 1% исходного файла
    :return: (oldSize, newSize, compression)
    """

    newName += "." + EXTENSION
    tree = HuffTree(filename=oldName, from_="file")
    codes = tree.getCodes()
    with open(oldName, "rb") as oldfile:
        with open(newName, "wb") as newfile:
            # Записываем данные об исходном расширении
            oldExt = pt.getExt(oldName)
            oldExtLen = len(oldExt)
            newfile.write(bytes([oldExtLen]))
            newfile.write(bytes([ord(char) for char in oldExt]))

            # Записываем данные о дереве
            newfile.write(tree.toBytes())

            # Записываем размер исходного файла в байтах
            oldFileSize = os.path.getsize(oldName)
            newfile.write(intToBytes(oldFileSize) + bytes([10]))

            # Записываем архивированные данные
            chunk_counter = 0
            nullByte = 0
            k = 7
            while True:
                if not RUN:
                    return ()
                chunk = oldfile.read(1)
                chunk_counter += 1
                if funcAfterPercent and int(chunk_counter / oldFileSize * 100) - int(
                        (chunk_counter - 1) / oldFileSize * 100) == 1:
                    funcAfterPercent()
                if not chunk:
                    if k < 7:
                        newfile.write(bytes([nullByte]))
                    break
                byte = ord(chunk)
                code = codes[byte]
                for bit in code:
                    if bit == "1":
                        nullByte |= (1 << k)
                    k -= 1
                    if k < 0:
                        k = 7
                        newfile.write(bytes([nullByte]))
                        nullByte = 0
    newFileSize = os.path.getsize(newName)
    return oldFileSize, newFileSize, getCompress(oldFileSize, newFileSize)


def toArchiveMany(filenames: tuple[(str, str)], funcAfterFile=None, funcAfterPercent=None) -> list:
    """
    :param filenames: (("oldName", "newDir/newNameWithoutExt"), ...)
    :param funcAfterFile: вызывается каждый раз после завершения архивирования очередного файла
    :param funcAfterPercent: вызывается каждый раз после обработки 1% очередного файла
    :return: список файлов, которые не удалось архивировать
    """

    global RUN
    RUN = True

    errLst = []
    for i in range(len(filenames)):
        oldName = filenames[i][0]
        newName = filenames[i][1]
        try:
            toArchive(oldName=oldName, newName=newName, funcAfterPercent=funcAfterPercent)
        except:
            errLst.append(oldName)
        if not RUN:
            return errLst
        if funcAfterFile:
            funcAfterFile()
    return errLst


def intToBytes(n: int) -> bytes:
    """
    :param n: число
    :return: объект bytes, в котором каждый байт равен числу-цифре числа n
    """
    return bytes(list(map(int, str(n))))


def bytesToInt(arrOfBytes: bytes) -> int:
    """
    Функция, обратная intToBytes
    """
    return int("".join(map(str, list(arrOfBytes))))


def fromArchive(oldName: str, newName: str, funcAfterPercent=None) -> None:
    """
    Создает файл, полученный из архива.
    :param oldName: путь к архиву
    :param newName: путь к извлеченному файлу без расширения
    :param funcAfterPercent: вызывается каждый раз после обработки 1% архива
    """

    tree = HuffTree(filename=oldName, from_="archive")
    with open(oldName, "rb") as oldfile:
        oldSize = os.path.getsize(oldName)

        # Считываем расширение исходного файла
        extLen = ord(oldfile.read(1))
        ext = "".join([chr(byte) for byte in oldfile.read(extLen)])

        newName += "." + ext
        with open(newName, "wb") as newfile:
            # Пропускаем данные о дереве
            oldfile.read(tree.lenInArchive())

            # Считываем размер исходного файла в байтах
            newfilesize = 0
            while True:
                byte = ord(oldfile.read(1))
                if byte == 10:
                    break
                newfilesize = newfilesize * 10 + byte

            # Разархивируем данные
            chunk_counter = 0
            topID = tree.getRootID()
            k_writed = 0
            breakFlag = False
            while not breakFlag:
                if not RUN:
                    return
                chunk = oldfile.read(1)
                chunk_counter += 1
                if funcAfterPercent and int(chunk_counter / oldSize * 100) - int(
                        (chunk_counter - 1) / oldSize * 100) == 1:
                    funcAfterPercent()
                if not chunk:
                    break
                byte = ord(chunk)
                for k in range(7, -1, -1):
                    bit = int(byte & (1 << k) > 0)
                    topID = tree.getNextTopID(topID, bit)
                    if tree.isLeaf(topID):
                        newfile.write(bytes([tree.getByte(topID)]))
                        k_writed += 1
                        if k_writed == newfilesize:
                            breakFlag = True
                            break
                        topID = tree.getRootID()
    if k_writed != newfilesize:
        raise Exception


def fromArchiveMany(filenames: tuple[(str, str)], funcAfterFile=None, funcAfterPercent=None) -> list:
    """
    Извлекает файлы из архивов.
    :param filenames: ([oldName, newDir/newNameWithoutExt], ...)
    :param funcAfterFile: вызывается каждый раз после извлечения из архива очередного файла
    :param funcAfterPercent: вызывается каждый раз после обработки 1% очередного файла
    :return: список файлов, которые не удалось извлечь из архива
    """

    global RUN
    RUN = True

    errLst = []
    for i in range(len(filenames)):
        oldName = filenames[i][0]
        newName = filenames[i][1]
        try:
            fromArchive(oldName=oldName, newName=newName, funcAfterPercent=funcAfterPercent)
        except:
            errLst.append(oldName)
        if not RUN:
            return errLst
        if funcAfterFile:
            funcAfterFile()
    return errLst


def getCompress(oldSize: int, newSize: int) -> float:
    """
    :param oldSize: размер исходного файла
    :param newSize: размер архива
    :return: на сколько процентов уменьшился размер исходного файла при заархивировании
    """
    if oldSize == 0:
        return -100.0
    return round(100 - newSize / oldSize * 100, 2)


def statisticOneFile(filename: str, tree: HuffTree) -> tuple:
    """
    Возвращает статистику для файла, который будет добавлен в архив.
    :param filename: путь к файлу для архивировния
    :param tree: HuffTree для файла
    :return: (oldSize, newSize, compression)
    """
    oldSize = os.path.getsize(filename)
    lenArchiveData = tree.lenArchiveData()
    newSize = 1 + len(pt.getExt(filename)) + tree.lenInArchive() + len(str(lenArchiveData)) + 1 + lenArchiveData
    compression = getCompress(oldSize, newSize)
    return oldSize, newSize, compression


def statisticManyFiles(filesData: list[(str, HuffTree)]) -> list:
    """
    Возвращает статистику для файлов, которые будут добавлены в архив.
    :param filesData: [(filename, HuffTree), ...]
    :return: [(filename, oldSize, newSize, compression), ..., ("ИТОГО", oldSize, newSize, compression)]
    """
    statistic = []
    sumOldSize = 0
    sumNewSize = 0
    for filePath, tree in filesData:
        oldSize, newSize, compression = statisticOneFile(filename=filePath, tree=tree)
        statistic.append((filePath, oldSize, newSize, compression))
        sumOldSize += oldSize
        sumNewSize += newSize
    sumCompression = getCompress(oldSize=sumOldSize, newSize=sumNewSize)
    statistic.append(("ИТОГО", sumOldSize, sumNewSize, sumCompression))
    return statistic


def preview(filenames: tuple[str], funcAfterPercent=None, funcAfterFile=None) -> list:
    """
    Ресурсозатратный statisticManyFiles()
    :return: [(filename, oldSize, newSize, compression), ..., ("ИТОГО", oldSize, newSize, compression)]
    """

    filesData = []
    for fileName in filenames:
        tree = HuffTree(filename=fileName, from_="file", funcAfterPercent=funcAfterPercent)
        filesData.append((fileName, tree))
        if not RUN:
            return []
        if funcAfterFile:
            funcAfterFile()
    statistic = statisticManyFiles(filesData=filesData)
    return statistic
