"""Unit tests for rank_candidates output format and max_tokens constant."""

import pytest
from unittest.mock import MagicMock, patch
import openai_example


def _call_rank_candidates(candidates, response_text=""):
    """Helper: call rank_candidates with minimal args and a mocked API response."""
    with patch.object(openai_example, 'get_anthropic_client') as mock_client_fn:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_text)]
        mock_client.messages.create.return_value = mock_response

        result = openai_example.rank_candidates(
            taste_profile={},
            candidates=candidates,
            liked_names=[],
            disliked_names=[],
            city="Chicago",
            liked_restaurant_objs=[],
            input_restaurant_objs=[],
        )
        call_kwargs = mock_client.messages.create.call_args[1]
        return result, call_kwargs


def _make_candidates(names):
    return [
        {
            'name': n, 'place_id': f'pid{i}', 'primary_type': 'restaurant',
            'price_level': None, 'rating': 4.0, 'editorial_summary': None,
            '_is_revisit': False,
        }
        for i, n in enumerate(names, 1)
    ]


class TestMaxTokens:
    def test_max_tokens_at_least_500(self):
        """Verify Haiku call uses >= 500 max_tokens to avoid rushed descriptions."""
        candidates = _make_candidates(['Alpha'])
        _, call_kwargs = _call_rank_candidates(candidates)
        assert call_kwargs['max_tokens'] >= 500, (
            f"max_tokens={call_kwargs['max_tokens']} is too low; must be >= 500"
        )


class TestCandidateLineFormatting:
    """Verify candidate metadata fields appear in the numbered list passed to Haiku."""

    def _get_prompt(self, candidates):
        _, call_kwargs = _call_rank_candidates(candidates)
        return call_kwargs['messages'][0]['content']

    def test_primary_type_in_candidate_line(self):
        candidates = [{
            'name': 'Tacos El Norte', 'place_id': 'x1',
            'primary_type': 'mexican_restaurant',
            'price_level': None, 'rating': None, 'editorial_summary': None,
            '_is_revisit': False,
        }]
        assert 'mexican_restaurant' in self._get_prompt(candidates)

    def test_rating_in_candidate_line(self):
        candidates = [{
            'name': 'Sushi Spot', 'place_id': 'x2',
            'primary_type': 'japanese_restaurant',
            'price_level': None, 'rating': 4.7, 'editorial_summary': None,
            '_is_revisit': False,
        }]
        assert '4.7' in self._get_prompt(candidates)

    def test_editorial_summary_in_candidate_line(self):
        candidates = [{
            'name': 'Pasta Palace', 'place_id': 'x3',
            'primary_type': 'italian_restaurant',
            'price_level': None, 'rating': None,
            'editorial_summary': 'Cozy neighborhood trattoria',
            '_is_revisit': False,
        }]
        assert 'Cozy neighborhood trattoria' in self._get_prompt(candidates)

    def test_revisit_tag_appears(self):
        candidates = [{
            'name': 'Old Favorite', 'place_id': 'x4',
            'primary_type': 'restaurant',
            'price_level': None, 'rating': 4.5, 'editorial_summary': None,
            '_is_revisit': True,
        }]
        assert '[previously recommended]' in self._get_prompt(candidates)


class TestOutputParsing:
    """Verify rank_candidates correctly parses Haiku's response lines."""

    def test_three_part_format_parsed(self):
        candidates = _make_candidates(['Alpha', 'Beta', 'Gamma'])
        response = (
            "1. Alpha - Because you liked X and Y - Great casual spot\n"
            "2. Beta - Because you liked X and Z - Upscale Mediterranean vibes\n"
            "3. Gamma - Because you liked Y and Z - Lively taqueria with bold flavors"
        )
        results, _ = _call_rank_candidates(candidates, response)
        assert len(results) == 3
        names = {r['name'] for r in results}
        assert names == {'Alpha', 'Beta', 'Gamma'}

    def test_empty_middle_section_parsed(self):
        """N. Name - - Description (no names cited) should still parse."""
        candidates = _make_candidates(['Alpha', 'Beta', 'Gamma'])
        response = (
            "1. Alpha - - Vibrant Mexican street food experience\n"
            "2. Beta - - Cozy Italian trattoria downtown\n"
            "3. Gamma - - Trendy rooftop bar with cocktails"
        )
        results, _ = _call_rank_candidates(candidates, response)
        assert len(results) == 3

    def test_reason_field_included_in_result(self):
        candidates = _make_candidates(['Alpha', 'Beta', 'Gamma'])
        response = (
            "1. Alpha - Because you liked X and Y - Excellent tacos in a casual setting\n"
            "2. Beta - Because you liked X - Fine dining French cuisine\n"
            "3. Gamma - - Lively sports bar downtown"
        )
        results, _ = _call_rank_candidates(candidates, response)
        alpha = next(r for r in results if r['name'] == 'Alpha')
        assert alpha.get('reason') is not None
        assert len(alpha['reason']) > 0
