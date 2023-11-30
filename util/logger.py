import logging as log
import util.load_env as env

log.basicConfig(filename=env.LOG_FILE, filemode='a', format='%(name)s - %(levelname)s - %(message)s')

def setup_logger(file_name, class_name, level_int):
    """
    Set up a logger object for a given file & class.
    DEFAULT level_int is ERROR.
    
    Parameters
    ----------
    file_name : str
        file where the logger is initiated
    class_name : str
        class name where the logger is initiated
    level_int : int
        Use 0=DEBUG, 1=INFO, 2=WARNING, 3=ERROR
        
    Returns
    ----------
    logger : logging object
        configured logging object 
    """
    logger = log.getLogger(f"{file_name} : {class_name}")
    
    if level_int == 0:
        level = log.DEBUG
    elif level_int == 1:
        level = log.INFO
    elif level_int == 2:
        level = log.WARNING
    else:
        level = log.ERROR

    logger.setLevel(level)
    return logger
