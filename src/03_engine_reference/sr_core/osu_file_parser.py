class parser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.od = -1
        self.column_count = -1
        self.columns = []
        self.note_starts = []
        self.note_ends = []
        self.note_types = []

    def process(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            try:
                for line in f:
                    self.read_metadata(f, line)

                    cc = self._read_column_count(line)
                    if cc != -1:
                        self.column_count = cc

                    self.od = 9

                    if self.column_count != -1:
                        self._read_notes(f, line, self.column_count)

            except StopIteration:
                pass

    def read_metadata(self, f, line):
        if "[Metadata]" in line:
            while "Source:" not in line:
                line = next(f)
                # Modern osu!lazer files (v128+) may omit the Source field.
                # Stop scanning when the next section begins so the
                # [HitObjects] block is still reachable by the main loop.
                if line.startswith("["):
                    break

    def _read_column_count(self, line):
        if "CircleSize:" not in line:
            return -1
        val = line.strip()[-1]
        if val == "0":
            val = "10"
        return int(float(val))

    def _read_notes(self, f, line, column_count):
        if "[HitObjects]" not in line:
            return
        line = next(f)
        while line is not None:
            line = line.strip()
            if not line:
                line = next(f)
                continue
            self._parse_hit_object(line, column_count)
            line = next(f)

    def _parse_hit_object(self, line, column_count):
        params = line.split(",")
        column_width = 512 // column_count
        self.columns.append(int(float(params[0])) // column_width)
        self.note_starts.append(int(params[2]))
        self.note_types.append(int(params[3]))
        self.note_ends.append(int(params[5].split(":")[0]))

    def get_parsed_data(self):
        return [
            self.column_count,
            self.columns,
            self.note_starts,
            self.note_ends,
            self.note_types,
            self.od,
        ]