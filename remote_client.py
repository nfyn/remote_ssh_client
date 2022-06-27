#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
-------------------------------------------------
  Filename: remote_client.py
  Desc    :  基于paramiko实现的远程连接客户端，支持ssh和scp
  Author  : nfyn
  Created : 2022/6/27
-------------------------------------------------
"""
import os
import stat
from typing import List, Optional, Tuple, NoReturn

from paramiko import SSHClient, AutoAddPolicy, MissingHostKeyPolicy
from paramiko.ssh_exception import AuthenticationException, SSHException

from custom_logger import logger


class RemoteClient:
    """
    基于paramiko实现的远程连接客户端
    功能：
    :func command: 执行单条命令
    :func execute_commands: 执行命令列表，可执行多条命令
    :func write_file: 写入内容都远程文件
    :func get_file: 获取远程文件或者文件夹到本地
    :func put_file: 上传本地文件或者文件夹到远程
    """
    def __init__(self, hostname, username, password, port=22):
        """
        构造函数初始化
        :param hostname: 主机ip
        :param username: 用户名
        :param password: 密码
        :param port: 端口，默认端口22
        """
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.client = None
        self.sftp = None

    def connect(self) -> NoReturn:
        """建立ssh连接"""
        try:
            self.client = SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(AutoAddPolicy())
            # self.client.set_missing_host_key_policy(MissingHostKeyPolicy())
            self.client.connect(hostname=self.hostname, port=self.port, username=self.username, password=self.password, timeout=5000)
            self.sftp = self.client.open_sftp()
        except AuthenticationException as e:
            logger.error(f"AuthenticationException occurred; did you remember to generate an SSH key? {e}")
        except Exception as e:
            logger.error(f"Unexpected error occurred while connecting to host: {e}")

    def disconnect(self) -> NoReturn:
        """关闭ssh连接"""
        if self.sftp:
            self.sftp.close()

        if self.client:
            self.client.close()

    def __enter__(self):
        """上下文管理器进入函数"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出函数"""
        self.disconnect()

    def command(self, command: str) -> Tuple[List[str], bool]:
        """
        执行shell命令
        :param command: 要执行的shell命令语句
        :return:
        """
        stdin, stdout, stderr = self.client.exec_command(command)
        info, is_success = (stdout, True) if stdout.channel.recv_exit_status() == 0 else (stderr, False)
        response = info.read().decode('utf-8', 'ignore').strip().split('\n')
        if is_success:
            logger.info(f"\nINPUT: {command}\nOUTPUT: {response}")
        else:
            logger.error(f"\nINPUT: {command}\nOUTPUT: {response}")

        return response, is_success

    def execute_commands(self, commands: List[str]) -> List[Tuple[List[str], bool]]:
        """
        Execute multiple commands in succession.

        :param List[str] commands: List of unix commands as strings.
        """

        return [self.command(cmd) for cmd in commands]

    def write_file(self, text: str, remote_file_path: str) -> NoReturn:
        """
        远程写可执行文件，并保持在远程主机上
        :param text: 写入内容
        :param remote_file_path: 写入的远程文件路径
        :return:
        """
        if self.is_remote_exist(remote_file_path) and self.is_remote_dir(remote_file_path):
            logger.error(f"错误：远程路径{remote_file_path}已经存在，并且为文件夹，无法正常写入")
            raise ValueError(f"错误：远程路径{remote_file_path}已经存在，并且为文件夹，无法正常写入")

        self.sftp.open(remote_file_path, 'w').write(text)
        self.sftp.chmod(remote_file_path, 755)

    def _get_one_file(self, remote_path: str, local_path: str) -> NoReturn:
        """
        从远程获取单个文件到本地文件或者文件夹
        :param remote_path: 远程单个文件路径
        :param local_path: 本地文件或者文件夹路径
        """
        if not self.is_remote_exist(remote_path):
            # 如果远程路径不存在，提示错误
            logger.error(f"错误：远程路径{remote_path}不存在")
            raise ValueError(f"错误：远程路径{local_path}不存在")

        if not os.path.exists(os.path.dirname(local_path)):
            # 如果本地路径父级文件夹不存在
            if local_path.endswith('/'):
                # 如果本地路径以'/'结尾，则创建文件夹
                os.makedirs(local_path, exist_ok=True)
            else:
                # 否则创建本地路径父级文件夹
                os.makedirs(os.path.dirname(local_path))

        if os.path.isdir(local_path):
            # 如果本地路径是文件夹，则拼接新的文件路径
            local_path = os.path.join(local_path, os.path.split(remote_path)[-1]).replace('\\', '/')

        # 最终获取文件，是从远程文件下载到本地文件
        self.sftp.get(remote_path, local_path)
        logger.info(f'接收：远程路径：{remote_path} -> 本地路径：{local_path}')

    def get_file(self, remote_path: str, local_path: str) -> NoReturn:
        """
        从远程获取（文件或者文件夹）到本地
        :param remote_path: 远程路径
        :param local_path: 本地路径
        """
        if not self.is_remote_exist(remote_path):
            logger.error(f"错误：远程路径{remote_path}不存在")
            raise ValueError(f"错误：远程路径{remote_path}不存在")

        if self.is_remote_dir(remote_path):
            # 如果远程路径是文件夹
            if not os.path.exists(local_path):
                # 如果本地路径不存在，创建本地路径为文件夹，否则本地路径可能为文件或者文件夹
                os.makedirs(local_path, exist_ok=True)

            if os.path.isdir(local_path):
                # 如果远程路径是文件夹
                for item in self.sftp.listdir(remote_path):
                    sub_remote_path = os.path.join(remote_path, item).replace('\\', '/')
                    sub_local_path = os.path.join(local_path, item).replace('\\', '/')
                    self.get_file(sub_remote_path, sub_local_path)
            else:
                # 如果本地路径是文件，提示错误，远程文件夹无法传输到本地文件
                logger.error(f"错误：本地路径{local_path}为文件，但远程路径{remote_path}为文件夹，无法传输")
                raise ValueError(f"错误：本地路径{local_path}为文件，但远程路径{remote_path}为文件夹，无法传输")

        elif self.is_remote_file(remote_path):
            # 如果远程路径是文件
            self._get_one_file(remote_path, local_path)

    def _put_one_file(self, local_path: str, remote_path: str) -> NoReturn:
        """
        上传本地单个文件到远程文件或者文件夹
        :param local_path: 本地单个文件路径
        :param remote_path: 远程文件或者文件夹路径
        """
        if not os.path.exists(local_path):
            # 如果本地路径不存在，提示错误
            logger.error(f"错误：本地路径{local_path}不存在")
            raise ValueError(f"错误：本地路径{local_path}不存在")

        if not self.is_remote_exist(os.path.dirname(remote_path)):
            # 如果远程路径父级文件夹不存在
            if remote_path.endswith('/'):
                # 如果远程路径以'/'结尾，则创建文件夹
                self.remote_makedir(remote_path)
            else:
                # 否则创建远程路径父级文件夹
                self.remote_makedir(os.path.dirname(remote_path))

        if self.is_remote_dir(remote_path):
            # 如果远程路径是文件夹，则拼接新的文件路径
            remote_path = os.path.join(remote_path, os.path.split(local_path)[-1]).replace('\\', '/')

        # 最终上传文件，是从本地文件上传到远程文件
        self.sftp.put(local_path, remote_path)
        logger.info(f'发送：本地路径：{local_path} -> 远程路径：{remote_path}')

    def put_file(self, local_path: str, remote_path: str) -> NoReturn:
        """
        从本地上传文件或者文件夹到远程
        :param local_path: 本地路径
        :param remote_path: 远程路径
        """
        if not os.path.exists(local_path):
            logger.error(f"错误：本地路径{local_path}不存在")
            raise ValueError(f"错误：本地路径{local_path}不存在")

        if os.path.isdir(local_path):
            # 如果本地路径是文件夹
            if not self.is_remote_exist(remote_path):
                # 如果远程路径不存在，创建远程路径为文件夹，否则远程路径可能为文件或者文件夹
                self.remote_makedir(remote_path)

            if self.is_remote_dir(remote_path):
                # 如果远程路径是文件夹
                for item in os.listdir(local_path):
                    sub_local_path = os.path.join(local_path, item).replace('\\', '/')
                    sub_remote_path = os.path.join(remote_path, item).replace('\\', '/')
                    self.put_file(sub_local_path, sub_remote_path)
            else:
                # 如果远程路径是文件，提示错误，本地文件夹无法传输到远程文件
                logger.error(f"错误：远程路径{remote_path}为文件，但本地路径{local_path}为文件夹，无法传输")
                raise ValueError(f"错误：远程路径{remote_path}为文件，但本地路径{local_path}为文件夹，无法传输")
        elif os.path.isfile(local_path):
            # 如果本地路径是文件
            self._put_one_file(local_path, remote_path)

    def is_remote_exist(self, path: str) -> bool:
        """
        判断远程路径是否存在
        :param path: 要判断的路径
        :return:
        """
        try:
            self.sftp.stat(path)
            return True
        except FileNotFoundError:
            return False

    def is_remote_dir(self, path: str) -> bool:
        """判断远程是否为文件夹"""
        try:
            return stat.S_ISDIR(self.sftp.stat(path).st_mode)
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def is_remote_file(self, path: str) -> bool:
        """判断远程是否为文件"""
        try:
            return stat.S_ISREG(self.sftp.stat(path).st_mode)
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def remote_makedir(self, path: str) -> bool:
        """
        在远程创建文件夹
        :param path: 要创建的路径
        """
        _, is_success = self.command(f"mkdir -p {path}")
        return is_success

    def remote_mkdir_p(self, path: str) -> Optional[bool]:
        """
        远程创建文件夹
        :param path: 要创建的路径
        """
        if path == '/':
            self.sftp.chdir('/')
            return

        if path == '':
            return

        try:
            self.sftp.chdir(path)
        except IOError:
            dirname, basename = os.path.split(path.rstrip('/'))
            self.remote_mkdir_p(dirname)
            self.sftp.mkdir(basename)
            self.sftp.chdir(basename)
            return True


if __name__ == '__main__':
    with RemoteClient(hostname='192.168.33.64', username='root', password='123456') as rc:
        # 执行远程命令
        rc.execute_commands(['pwd', 'ls'])
        # 获取远程文件
        rc.get_file('/root/2', 'd:/3')
        # 上传本地文件
        rc.put_file('d:/3', '/root/4')

