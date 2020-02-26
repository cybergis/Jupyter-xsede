import os
import tempfile
import shutil
import logging


logger = logging.getLogger("cybergis")
logger.setLevel("INFO")
streamHandler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


def get_logger():
    logger = logging.getLogger("cybergis")
    return logger


class UtilsMixin(object):

    def remove_newlines(self, in_str):
        out_str = in_str.replace("\r", "").replace("\n", "")
        return out_str

    def zip_local_folder(self, local_dir, output_dir=None):
        """
        Zip up a local folder /A/B/C, output zip filename: C.zip
        :param local_dir: Path to a local folder: /A/B/C
        :param output_dir: where to put C.zip in; default(None): put C.zip in a random temp folder
        :return: full path to output zip file C.zip
        """
        if not os.path.isdir(local_dir):
            raise Exception("Not a folder: {}".format(local_dir))
        folder_name = os.path.basename(local_dir)
        parent_path = os.path.dirname(local_dir)
        if output_dir is None:
            output_fprefix = os.path.join(tempfile.mkdtemp(), folder_name)
        else:
            output_fprefix = os.path.join(output_dir, folder_name)
        shutil.make_archive(output_fprefix, "zip", parent_path, folder_name)
        zip_fpath = output_fprefix + ".zip"
        logger.debug("Zipping folder {} to {}".format(local_dir, zip_fpath))
        return zip_fpath

    def create_local_folder(self, folder_path):

        logger.debug("Creating local folder: {}".format(folder_path))
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    def copy_local(self, source, target):
        """
        file --> file
        file --> target/file
        folder --> target/folder
        :param source:
        :param target:
        :return:
        """
        if not os.path.exists(source):
            raise Exception("Source does not exist")
        source_is_folder = os.path.isdir(source)
        target_exists = os.path.exists(target)
        target_is_file = os.path.isfile(target)

        if source_is_folder:
            if target_exists:
                source_folder_name = os.path.basename(source)
                target = os.path.join(target, source_folder_name)
            shutil.copytree(source, target)
        else:  # source is file
            if target_is_file:
                raise Exception("Target file exists")
            shutil.copy(source, target)

        logger.debug("Local copying {} to {}".format(source, target))

    def move_local(self, source, target):
        """
        file --> file
        file --> target/file
        folder --> target/folder
        :param source:
        :param target:
        :return:
        """
        logger.debug("Local moving {} to {}".format(source, target))
        shutil.move(source, target)

    def replace_text_in_file(self, local_source_file_path, replacement_list, local_new_file_path=None):

        with open(local_source_file_path, 'r') as f:
            filedata = f.read()
        for pair in replacement_list:
            filedata = filedata.replace(pair[0], pair[1])
        if local_new_file_path is None:
            local_new_file_path = local_source_file_path
        with open(local_new_file_path, 'w') as file:
            file.write(filedata)
        logger.debug("New file saved to {}".format(local_new_file_path))

    def _check_abs_path(self, in_path, raise_on_false=False):
        out_path = in_path
        if not os.path.isabs(in_path):
            if raise_on_false:
                raise Exception("{} is not a absolute path".format(in_path))
            else:
                out_path = os.path.abspath(out_path)
                logger.warning("Convert path {} to {}".format(in_path, out_path))
        return out_path
