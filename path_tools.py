import os


def getExt(filename: str) -> str:
    """
    :return: расширение файла без точки
    """
    return os.path.splitext(os.path.basename(filename))[1][1:]
