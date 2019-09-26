import os
import tempfile
import shutil
import logging

logger = logging.getLogger("cybergis")


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