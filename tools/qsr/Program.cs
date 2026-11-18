//! qsr -- Quaver Skill Rating for an osu!mania chart, as a JSON filter.
//!
//!   qsr <file.osu>
//!   stdout: {"qsr": 18.42, "keycount": 4, "valid": true, "notes": 2082}
//!
//! Quaver's own parser reads .osu directly, so no conversion step is needed
//! outside this program. The rating is the calculator's OverallDifficulty.
//!
//! `valid` and `notes` are reported because the converter silently yields a
//! partial map for some inputs, and a rating computed from a truncated map is
//! worse than no rating at all.

using System;
using System.IO;
using System.Text.Json;
using Quaver.API.Enums;
using Quaver.API.Maps;
using Quaver.API.Maps.Parsers;
using Quaver.API.Maps.Processors.Difficulty;

namespace Qsr
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            if (args.Length < 1)
            {
                Console.Error.WriteLine("usage: qsr <file.osu>");
                return 2;
            }

            var path = args[0];
            if (!File.Exists(path))
            {
                Console.Error.WriteLine($"qsr: not found: {path}");
                return 2;
            }

            try
            {
                var osu = new OsuBeatmap(path);
                Qua qua = osu.ToQua();
                int notes = qua.HitObjects.Count;

                DifficultyProcessor processor = qua.SolveDifficulty();
                float qsr = processor.OverallDifficulty;

                var result = new
                {
                    qsr = (double)qsr,
                    keycount = qua.GetKeyCount(),
                    valid = osu.IsValid && notes > 0,
                    notes = notes,
                };
                Console.WriteLine(JsonSerializer.Serialize(result));
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"qsr: {ex.GetType().Name}: {ex.Message}");
                return 3;
            }
        }
    }
}
