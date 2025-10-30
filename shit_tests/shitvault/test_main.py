"""
Tests for shitvault/__main__.py - CLI entry point.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock

# The shitvault.__main__ module just calls asyncio.run(main()) where main is from shitvault.cli
# So we need to test that it calls shitvault.cli.main


class TestModuleMain:
    """Test cases for __main__.py entry point."""

    def test_main_is_imported_from_cli(self):
        """Test that __main__ imports main from cli."""
        from shitvault import __main__
        import shitvault.cli
        assert __main__.main is shitvault.cli.main

    def test_main_is_async(self):
        """Test that main function is async."""
        import inspect
        from shitvault.cli import main
        assert inspect.iscoroutinefunction(main)

    @pytest.mark.asyncio
    async def test_main_can_be_called(self):
        """Test that main can be called directly."""
        with patch('shitvault.cli.create_database_parser') as mock_create_parser:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = 'stats'
            mock_parser.parse_args.return_value = mock_args
            mock_create_parser.return_value = mock_parser
            
            with patch('shitvault.cli.get_database_stats') as mock_get_stats:
                from shitvault.cli import main
                await main()
                
                mock_get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_handles_exceptions(self):
        """Test that main handles exceptions."""
        with patch('shitvault.cli.create_database_parser') as mock_create_parser:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = 'stats'
            mock_parser.parse_args.return_value = mock_args
            mock_create_parser.return_value = mock_parser
            
            with patch('shitvault.cli.get_database_stats') as mock_get_stats:
                mock_get_stats.side_effect = Exception("Test error")
                
                from shitvault.cli import main
                with pytest.raises(SystemExit):
                    await main()

