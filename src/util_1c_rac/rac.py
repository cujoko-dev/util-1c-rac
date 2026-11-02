import platform
import time
from pathlib import Path

from loguru import logger

from . import base

_NAME_RESOLUTION_ATTEMPTS = 3
_NAME_RESOLUTION_RETRY_DELAY = 2


class InfobaseNotFound(Exception):
    pass


class Cluster:
    def __init__(
        self,
        host: str = platform.node(),
        port: int = 1541,
        ras_host: str = platform.node(),
        ras_port: int = 1545,
        *,
        rac_file_fullpath: Path | None,
    ):
        """Class to manage cluster infobase and cluster settings.
        Args:
            - host              (str)  -- Cluster host
            - port              (int)  -- Cluster port
            - ras_host          (str)  -- RAS host
            - ras_port          (int)  -- RAS port
            - rac_file_fullpath (Path) -- Full path to rac.exe file
        """
        self.host = host
        self.port = port

        self.ras_host = ras_host
        self.ras_port = ras_port

        if rac_file_fullpath is None or not rac_file_fullpath.exists():
            raise FileNotFoundError(f"RAC file not found: {rac_file_fullpath}")

        self.rac_file_fullpath = rac_file_fullpath

        self._cluster_id = None

        output = self._run_command("cluster list", "get list of clusters")
        output_processed = self._process_output(output)

        if len(output_processed) > 0:
            output_processed_item = None

            for output_processed_item in output_processed:
                if output_processed_item["host"] == self.host and output_processed_item[
                    "port"
                ] == str(self.port):
                    break

            if output_processed_item:
                self._cluster_id = output_processed_item["cluster"]

        self.infobases = self._get_list_of_infobases()

    def _run_command(self, command: str, desc: str):
        commands = [
            f'"{self.rac_file_fullpath}" {self.ras_host}:{self.ras_port}',
            command,
        ]

        for attempt in range(1, _NAME_RESOLUTION_ATTEMPTS + 1):
            try:
                return base.run_command(" ".join(commands), desc)
            except ChildProcessError as exc:
                lines = str(exc).splitlines()
                endpoint = f"{self.ras_host}:{self.ras_port}".casefold()
                resolution_failed = any(
                    lines[i - 1].casefold().endswith("ошибка соединения с сервером")
                    and lines[i].strip().casefold() == endpoint
                    and lines[i + 1].strip().casefold() == "no such host is known"
                    for i in range(1, len(lines) - 1)
                )
                if not resolution_failed or attempt == _NAME_RESOLUTION_ATTEMPTS:
                    raise
                logger.warning(
                    "Cannot resolve RAS host {}; retrying in {} seconds (attempt {}/{})",
                    self.ras_host,
                    _NAME_RESOLUTION_RETRY_DELAY,
                    attempt + 1,
                    _NAME_RESOLUTION_ATTEMPTS,
                )
                time.sleep(_NAME_RESOLUTION_RETRY_DELAY)

    @staticmethod
    def _process_output(output):
        objs = []

        obj = None

        for line in output:
            if not line or obj is None:
                if obj is not None and len(obj) == 0:
                    continue  # Очередная пустая строка подряд

                obj = {}
                objs.append(obj)

            line_split = line.split(":", maxsplit=1)

            if len(line_split) >= 2:
                key, value = [x.strip() for x in line_split]

                obj[key] = value

        if obj is not None and len(obj) == 0:
            del objs[-1]

        return objs

    @staticmethod
    def _check_value(value, valid_values):
        """Checks the value for validity.
        Args:
            - value        (str)  -- value for check
            - valid_values (list) -- list of valid values
        """
        if value not in valid_values:
            raise ValueError(f"Invalid value {value}. Available values: {valid_values}")

    def infobase_exists(self, ib_name):
        try:
            ib_id = base.get_value_by_key_in_dicts_list(ib_name, self.infobases)
        except Exception:
            return False
        return True

    def _get_infobase_id(self, ib_name):
        try:
            ib_id = base.get_value_by_key_in_dicts_list(ib_name, self.infobases)
        except Exception:
            raise InfobaseNotFound(f'Could not find the infobase: "{ib_name}"')
        return ib_id

    def _get_list_of_infobases(self):
        output = self._run_command(
            f"infobase --cluster={self._cluster_id} summary list",
            "get list of infobases",
        )
        list_of_ib = self._process_output(output)

        return [{i["name"]: i["infobase"]} for i in list_of_ib]

    @staticmethod
    def _add_user_credentials(command, username="", pwd=""):
        if username:
            command += f" --infobase-user={username} --infobase-pwd={pwd}"
        return command

    # def create_infobase(self, ib_name, sql_server=""):
    #     """Create new infobase in cluster.
    #     Args:
    #         ib_name (str): infobase name
    #         sql_server (str): name of SQL server from settings file
    #     """
    #     settings = self.all_settings["variables"]["SQL_SERVERS"]

    #     if sql_server:
    #         db = settings[sql_server]
    #     else:
    #         db = settings[self.sql_server]

    #     command = (
    #         f"infobase --cluster={self._cluster_id}"
    #         f" create --create-database --name={ib_name}"
    #         f' --dbms={db["DBMS"]} --db-server={db["DB_HOST"]}'
    #         f' --db-user={db["DB_USER"]} --db-pwd={db["DB_PASSWORD"]}'
    #         f" --db-name={ib_name} --date-offset=2000 --security-level=1"
    #         f" --license-distribution=allow --locale=ru"
    #     )

    #     output = self._run_command(command, f'create infobase "{ib_name}"')
    #     infobase_id = self._process_output(output)[0]["infobase"]

    #     return infobase_id

    # def drop_infobase(self, ib_name, username, pwd, mode=""):
    #     """Drop infobase.
    #     Args:
    #         - ib_name  (str) -- infobase name
    #         - username (str) -- infobase administrator username
    #         - pwd      (str) -- infobase administrator password
    #         - mode     (str) -- mode of deleting database
    #             available value:
    #                 clear-database -- clear database
    #                 drop-database  -- delete database
    #     """
    #     infobase_id = self._get_infobase_id(ib_name)
    #     command = f"infobase --cluster={self._cluster_id} drop --infobase={infobase_id}"

    #     if mode:
    #         self._check_value(mode, ["clear-database", "drop-database"])
    #         command += f"--{mode}"

    #     command = self._add_user_credentials(command, username, pwd)

    #     self._run_command(command, f'drop infobase "{ib_name}"')

    def _set_option(self, ib_name, option, mode, username="", pwd=""):
        ib_id = self._get_infobase_id(ib_name)

        command = f"infobase --cluster={self._cluster_id} update --infobase={ib_id} --{option}={mode}"
        command = self._add_user_credentials(command, username, pwd)

        self._run_command(
            command, f'setting "{option}" to "{mode}" of infobase "{ib_name}"'
        )

    def set_schedule_jobs_lock(self, ib_name, mode, username, pwd):
        if self._check_value(mode, ["on", "off"]):
            return

        self._set_option(
            ib_name, option="scheduled-jobs-deny", mode=mode, username=username, pwd=pwd
        )

        time.sleep(1)

    def set_session_lock(self, ib_name, mode, username, pwd):
        if self._check_value(mode, ["on", "off"]):
            return

        self._set_option(
            ib_name, option="sessions-deny", mode=mode, username=username, pwd=pwd
        )

        time.sleep(1)

    def _get_sessions_list(self, ib_name):
        ib_id = self._get_infobase_id(ib_name)

        if ib_id is None:
            return

        command = f"session --cluster={self._cluster_id} list --infobase={ib_id}"

        output = self._run_command(command, f'get session list of infobase "{ib_name}"')
        session_list = self._process_output(output)

        return session_list

    def terminate_sessions(self, ib_name, session_number=""):
        """Terminate infobase sessions.
        Args:
            - ib_name        (str)      -- infobase name
            - session_number (str, int) -- session number, if not set, then all sessions terminate
        """
        sessions = self._get_sessions_list(ib_name)

        if sessions is None:
            raise AttributeError("sessions is None")

        for session in sessions:
            if session["session-id"] == str(session_number) or not session_number:
                command = f"session --cluster={self._cluster_id} terminate --session={session['session']}"

                try:
                    self._run_command(
                        command, f'terminate sessions of infobase "{ib_name}"'
                    )
                except Exception as exc:
                    logger.critical(f"failed to end session: {exc}")

        time.sleep(3)


class ClusterError(Exception):
    def __init__(self, text):
        self.txt = text
