# =============================================================================
# Copyright 2021 Henrique Morimitsu
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

from pathlib import Path
import shutil

import summary_metrics


def test_summary(tmp_path: Path) -> None:
    parser = summary_metrics._init_parser()
    args = parser.parse_args([])
    args.metrics_path = Path("docs/source/results/metrics_all.csv")
    args.output_dir = tmp_path
    summary_metrics.summarize(args)

    assert len(list(tmp_path.glob("**/*.md"))) > 0
    assert len(list(tmp_path.glob("**/*.csv"))) > 0

    shutil.rmtree(tmp_path)
