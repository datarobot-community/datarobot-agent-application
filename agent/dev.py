# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""IDE-friendly development server entrypoint.

Runs ``nat dragent serve`` in-process so IDE debuggers (VS Code, PyCharm) can
attach and hit breakpoints in agent code. NAT serves the workflow with
``await uvicorn.Server(...).serve()`` only when it runs single-worker without
reload; both hold here, so the whole server stays in this process. For terminal
use prefer the ``dev`` Task, which runs ``nat dragent serve`` directly (with
reload).
"""

from datarobot_genai.dragent.cli.commands import dragent_command

from agent import Config


def main() -> None:
    config = Config()

    port = str(config.local_dev_port)
    print(f"Running development server on http://localhost:{port}")

    dragent_command.main(
        args=["serve", "--config_file", "workflow.yaml", "--port", port],
        standalone_mode=False,
    )


if __name__ == "__main__":
    main()
