import unittest

from scripts.aggregate_ratings import aggregate_ratings, normalize_external_payload, parse_rating_body


class RatingAggregationTests(unittest.TestCase):
    def setUp(self):
        self.conferences = [{"id": "conf-1", "review_status": "verified"}]

    def issue(self, number, author, rating, participation="attended", created_at="2026-06-19T00:00:00Z"):
        return {
            "number": number,
            "title": "[研討會評分] conf-1 Conference",
            "author": {"login": author},
            "createdAt": created_at,
            "body": (
                "conference_id: conf-1\n"
                f"rating: {rating}\n"
                "agenda_quality: 5\n"
                "review_transparency: 4\n"
                "organizer_communication: 4\n"
                "networking_value: 5\n"
                "cost_value: 4\n"
                f"participation: {participation}\n"
                "confirmed: true\n\n"
                f"comment:\n{author} 覺得很值得參加，議程安排完整，主辦單位通知清楚，交流品質也不錯"
            ),
        }

    def external_vote(self, voter_id, rating=4, comment="議程安排完整，主辦單位通知清楚，交流品質也不錯", submitted_at="2026-06-19T00:00:00Z"):
        return {
            "conference_id": "conf-1",
            "rating": rating,
            "dimensions": {
                "agenda_quality": 5,
                "review_transparency": 4,
                "organizer_communication": 4,
                "networking_value": 5,
                "cost_value": 4,
            },
            "participation": "attended",
            "confirmed": True,
            "voter_id": voter_id,
            "comment": comment,
            "submitted_at": submitted_at,
        }

    def test_parse_rating_body_keeps_multiline_comment(self):
        values = parse_rating_body("rating: 5\ncomment:\n第一行\n第二行")
        self.assertEqual(values["rating"], "5")
        self.assertEqual(values["comment"], "第一行\n第二行")

    def test_aggregates_valid_attendee_votes(self):
        payload, results = aggregate_ratings(
            [self.issue(1, "alice", 5), self.issue(2, "bob", 3, "registered")],
            self.conferences,
        )
        summary = payload["ratings"]["conf-1"]
        self.assertEqual(summary["average"], 4)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["attended_count"], 1)
        self.assertEqual(summary["registered_count"], 1)
        self.assertEqual(summary["dimension_averages"]["agenda_quality"], 5)
        self.assertTrue(results[1]["valid"])

    def test_latest_vote_from_same_github_user_wins(self):
        payload, _ = aggregate_ratings(
            [
                self.issue(1, "Alice", 2, created_at="2026-06-18T00:00:00Z"),
                self.issue(2, "alice", 5, created_at="2026-06-19T00:00:00Z"),
            ],
            self.conferences,
        )
        self.assertEqual(payload["ratings"]["conf-1"]["average"], 5)
        self.assertEqual(payload["rating_count"], 1)

    def test_rejects_unconfirmed_or_unknown_conference_vote(self):
        issue = self.issue(3, "alice", 5)
        issue["body"] = issue["body"].replace("confirmed: true", "confirmed: false")
        payload, results = aggregate_ratings([issue], self.conferences)
        self.assertEqual(payload["ratings"], {})
        self.assertFalse(results[3]["valid"])

    def test_aggregates_external_rating_api_votes(self):
        payload, _ = aggregate_ratings(
            [],
            self.conferences,
            [self.external_vote("browser-1")],
        )
        self.assertEqual(payload["ratings"]["conf-1"]["average"], 4)
        self.assertEqual(payload["rating_count"], 1)

    def test_latest_vote_from_same_external_voter_wins(self):
        payload, _ = aggregate_ratings(
            [],
            self.conferences,
            [
                self.external_vote("browser-1", rating=2, submitted_at="2026-06-18T00:00:00Z"),
                self.external_vote("browser-1", rating=5, comment="第二次評分補充原因較完整，確認活動整體品質很好", submitted_at="2026-06-19T00:00:00Z"),
            ],
        )
        self.assertEqual(payload["ratings"]["conf-1"]["average"], 5)
        self.assertEqual(payload["rating_count"], 1)

    def test_rejects_rating_without_dimensions_or_reason(self):
        issue = self.issue(4, "alice", 5)
        issue["body"] = "conference_id: conf-1\nrating: 5\nparticipation: attended\nconfirmed: true\n\ncomment:\n太棒"
        payload, results = aggregate_ratings([issue], self.conferences)
        self.assertEqual(payload["ratings"], {})
        self.assertFalse(results[4]["valid"])

    def test_flags_duplicate_reasons_out_of_average(self):
        repeated = "這場研討會整體安排清楚，議程和交流都符合研究生需求"
        payload, _ = aggregate_ratings(
            [],
            self.conferences,
            [self.external_vote("browser-1", 5, repeated), self.external_vote("browser-2", 1, repeated)],
        )
        summary = payload["ratings"]["conf-1"]
        self.assertEqual(summary["count"], 0)
        self.assertEqual(summary["flagged_count"], 2)
        self.assertEqual(payload["flagged_rating_count"], 2)

    def test_normalizes_external_payload_wrappers(self):
        self.assertEqual(normalize_external_payload({"ratings": [{"conference_id": "conf-1"}]}), [{"conference_id": "conf-1"}])


if __name__ == "__main__":
    unittest.main()
