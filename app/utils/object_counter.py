from ultralytics.solutions.solutions import BaseSolution, SolutionAnnotator, SolutionResults
from ultralytics.utils.plotting import colors

class ObjectCounter(BaseSolution):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.in_count = 0
        self.out_count = 0
        self.counted_ids = []
        self.classwise_counts = {}
        self.region_initialized = False
        self.boxes = []
        self.clss = []
        self.track_ids = []
        self.show_in = self.CFG.get("show_in", True)
        self.show_out = self.CFG.get("show_out", True)
        self.margin = self.line_width * 2

    def count_objects(self, current_centroid, track_id, prev_position, cls):
        if prev_position is None or track_id in self.counted_ids:
            return

        if len(self.region) == 2:
            line = self.LineString(self.region)
            if line.intersects(self.LineString([prev_position, current_centroid])):
                vertical = abs(self.region[0][0] - self.region[1][0]) < abs(self.region[0][1] - self.region[1][1])
                direction = (current_centroid[0] > prev_position[0]) if vertical else (current_centroid[1] > prev_position[1])
                if direction:
                    self.in_count += 1
                    self.classwise_counts[self.names[cls]]["IN"] += 1
                else:
                    self.out_count += 1
                    self.classwise_counts[self.names[cls]]["OUT"] += 1
                self.counted_ids.append(track_id)

        elif len(self.region) > 2:
            polygon = self.Polygon(self.region)
            if polygon.contains(self.Point(current_centroid)):
                region_width = max(p[0] for p in self.region) - min(p[0] for p in self.region)
                region_height = max(p[1] for p in self.region) - min(p[1] for p in self.region)
                direction = (region_width < region_height and current_centroid[0] > prev_position[0]) or \
                            (region_width >= region_height and current_centroid[1] > prev_position[1])
                if direction:
                    self.in_count += 1
                    self.classwise_counts[self.names[cls]]["IN"] += 1
                else:
                    self.out_count += 1
                    self.classwise_counts[self.names[cls]]["OUT"] += 1
                self.counted_ids.append(track_id)

    def store_classwise_counts(self, cls):
        name = self.names[cls]
        if name not in self.classwise_counts:
            self.classwise_counts[name] = {"IN": 0, "OUT": 0}

    def display_counts(self, plot_im):
        labels_dict = {
            key.capitalize(): " ".join([
                f"IN {val['IN']}" if self.show_in and val['IN'] else "",
                f"OUT {val['OUT']}" if self.show_out and val['OUT'] else ""
            ]).strip()
            for key, val in self.classwise_counts.items()
            if val['IN'] or val['OUT']
        }
        if labels_dict:
            self.annotator.display_analytics(plot_im, labels_dict, (104, 31, 17), (255, 255, 255), self.margin)

    def process(self, im0):
        if not self.region_initialized:
            self.initialize_region()
            self.region_initialized = True

        self.extract_tracks(im0)
        self.annotator = SolutionAnnotator(im0, line_width=self.line_width)
        self.annotator.draw_region(reg_pts=self.region, color=(104, 0, 123), thickness=self.line_width * 2)

        for box, track_id, cls in zip(self.boxes, self.track_ids, self.clss):
            self.store_tracking_history(track_id, box)
            self.store_classwise_counts(cls)
            current_centroid = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            prev_position = self.track_history[track_id][-2] if len(self.track_history[track_id]) > 1 else None
            self.count_objects(current_centroid, track_id, prev_position, cls)

        plot_im = self.annotator.result()
        self.display_counts(plot_im)

        return SolutionResults(
            plot_im=plot_im,
            in_count=self.in_count,
            out_count=self.out_count,
            classwise_count=self.classwise_counts,
            total_tracks=len(self.track_ids),
        )
