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
import pulumi


class _Mocks(pulumi.runtime.Mocks):
    def new_resource(self, args):
        return [f"{args.name}_id", args.inputs]

    def call(self, args):
        return {}


# Module-level on purpose: this must run before pytest imports the test
# modules, because infra.infra resolves the active stack and registers
# Pulumi resources at import time.
pulumi.runtime.set_mocks(_Mocks(), stack="unittest", preview=False)
