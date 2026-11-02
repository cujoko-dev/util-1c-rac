import subprocess as sub

import yaml
from loguru import logger


def read_settings():
    """Прочитать настройки"""

    with open("settings.yaml", "r", encoding="utf-8") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logger.critical(exc)


def get_value_by_key_in_dicts_list(key, list_of_dictionaries):
    """Получить значение по ключу в списке словарей"""

    return [element[key] for element in list_of_dictionaries if element.get(key)][0]


def get_cluster_by_version(version):
    """Получить кластер по версии"""

    settings = read_settings()

    if settings is None:
        raise AttributeError("settings is None")

    clusters = settings["variables"]["CLUSTERS"]
    for cluster in clusters:
        if clusters[cluster]["version"] == version:
            return cluster


def _decode_rac_output(data: bytes) -> str:
    """Decode modern RAC output while retaining support for older OEM output."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp866")


def run_command(command: str, desc: str):
    """Запустить команду"""

    try:
        proc = sub.Popen(command, stdout=sub.PIPE, stderr=sub.PIPE)
        outs, errs = proc.communicate()
        if errs:
            raise ChildProcessError(f"Error {_decode_rac_output(errs)} when {desc}")
        else:
            output = _decode_rac_output(outs)
    except Exception as exc:
        raise exc

    return output.split("\r\n")


def get_cluster_and_ib_name(connection_string):
    """Получить кластер и имя ИБ"""

    connection_string = connection_string.replace('";', "")
    connection_string = connection_string.replace('Srvr="', "")
    cluster, ib_name = connection_string.split('Ref="')
    return cluster, ib_name
