"""
Board Image Manager for P2P Encrypted BBS.

Manages board images by storing them in an application-managed directory
and storing relative paths in the database for consistency across restarts.
"""

import logging
import shutil
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class BoardImageManager:
    """Manages board images with centralized storage and relative path handling."""

    def __init__(self, app_data_dir: Path):
        """
        Initialize board image manager.

        Args:
            app_data_dir: Application data directory (typically ~/.bbs_p2p)
        """
        self.app_data_dir = Path(app_data_dir)
        self.board_images_dir = self.app_data_dir / "board_images"
        self.board_images_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Board image manager initialized: {self.board_images_dir}")

    def copy_board_image(self, source_path: str, board_id: str) -> Optional[str]:
        """
        Copy a board image from user-selected location into managed directory.

        Stores the image with a filename based on board_id to avoid conflicts.
        Returns a relative path for DB storage.

        Args:
            source_path: Path to the selected image file
            board_id: Board ID (used as filename basis)

        Returns:
            Relative path from app_data_dir to stored image, or None on error
        """
        try:
            if not source_path or not Path(source_path).exists():
                logger.warning(f"Source image does not exist: {source_path}")
                return None

            source = Path(source_path)

            # Validate file type (basic check)
            allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
            if source.suffix.lower() not in allowed_extensions:
                logger.warning(f"Image type not supported: {source.suffix}")
                return None

            # Generate filename: board_id + original extension
            dest_filename = f"{board_id}{source.suffix.lower()}"
            dest_path = self.board_images_dir / dest_filename

            # Copy file
            shutil.copy2(source, dest_path)
            logger.info(f"Copied board image: {source} -> {dest_path}")

            # Return relative path from app_data_dir
            relative_path = str(dest_path.relative_to(self.app_data_dir))
            return relative_path

        except Exception as e:
            logger.error(f"Failed to copy board image: {e}")
            return None

    def get_image_path(self, relative_path: Optional[str]) -> Optional[Path]:
        """
        Resolve a relative path to an absolute image path.

        Args:
            relative_path: Relative path stored in DB

        Returns:
            Absolute Path if image exists, None otherwise
        """
        if not relative_path:
            return None

        try:
            abs_path = self.app_data_dir / relative_path

            if abs_path.exists():
                return abs_path
            else:
                logger.warning(f"Board image not found: {abs_path}")
                return None

        except Exception as e:
            logger.error(f"Failed to resolve image path: {e}")
            return None

    def delete_board_image(self, relative_path: Optional[str]) -> bool:
        """
        Delete a board image file.

        Args:
            relative_path: Relative path stored in DB

        Returns:
            True if deleted successfully, False otherwise
        """
        if not relative_path:
            return False

        try:
            abs_path = self.app_data_dir / relative_path

            if abs_path.exists():
                abs_path.unlink()
                logger.info(f"Deleted board image: {abs_path}")
                return True
            else:
                logger.warning(f"Image file not found for deletion: {abs_path}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete board image: {e}")
            return False

    def cleanup_orphaned_images(self, active_board_ids: list) -> int:
        """
        Clean up orphaned image files (images not referenced by any board).

        Args:
            active_board_ids: List of board IDs currently in use

        Returns:
            Number of files deleted
        """
        try:
            deleted_count = 0

            for image_file in self.board_images_dir.iterdir():
                if not image_file.is_file():
                    continue

                # Check if filename (without extension) matches any active board ID
                filename_without_ext = image_file.stem
                if filename_without_ext not in active_board_ids:
                    image_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted orphaned image: {image_file}")

            logger.info(f"Cleaned up {deleted_count} orphaned board images")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned images: {e}")
            return 0
