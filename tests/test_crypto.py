"""
Unit tests for CryptoManager

Tests cover:
- Identity generation
- Signing and verification
- Encryption and decryption (sealed box)
- Session key derivation
- AEAD encryption/decryption
- Keystore save/load
"""

import os
import tempfile
from pathlib import Path

import pytest

from core.crypto_manager import (
    CryptoManager,
    Identity,
    CryptoError,
    SignatureVerificationError,
    DecryptionError,
    KeystoreError
)


@pytest.fixture
def crypto_manager():
    """Fixture providing a CryptoManager instance"""
    return CryptoManager()


@pytest.fixture
def identity(crypto_manager):
    """Fixture providing a generated identity"""
    return crypto_manager.generate_identity()


@pytest.fixture
def temp_keystore_path():
    """Fixture providing a temporary path for keystore files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_keystore.enc"


class TestIdentityGeneration:
    """Tests for identity generation"""
    
    def test_generate_identity_creates_valid_keypairs(self, crypto_manager):
        """Test that generate_identity produces valid Ed25519 and X25519 keypairs"""
        identity = crypto_manager.generate_identity()
        
        assert identity is not None
        assert identity.signing_private_key is not None
        assert identity.signing_public_key is not None
        assert identity.encryption_private_key is not None
        assert identity.encryption_public_key is not None
        assert identity.peer_id is not None
        assert identity.created_at is not None
    
    def test_peer_id_is_hex_string(self, identity):
        """Test that peer_id is a valid hex string"""
        assert isinstance(identity.peer_id, str)
        assert len(identity.peer_id) == 64  # SHA-256 produces 32 bytes = 64 hex chars
        # Verify it's valid hex
        int(identity.peer_id, 16)
    
    def test_peer_id_is_deterministic(self, crypto_manager, identity):
        """Test that peer_id is consistently derived from the same public key"""
        # Derive peer_id again from the same public key
        peer_id_2 = crypto_manager._derive_peer_id(identity.signing_public_key)
        assert identity.peer_id == peer_id_2
    
    def test_different_identities_have_different_peer_ids(self, crypto_manager):
        """Test that different identities produce different peer_ids"""
        identity1 = crypto_manager.generate_identity()
        identity2 = crypto_manager.generate_identity()
        
        assert identity1.peer_id != identity2.peer_id


class TestSigningAndVerification:
    """Tests for Ed25519 signing and verification"""
    
    def test_sign_and_verify_valid_data(self, crypto_manager, identity):
        """Test signing and verification with valid data"""
        data = b"Hello, BBS!"
        
        # Sign the data
        signature = crypto_manager.sign_data(data, identity.signing_private_key)
        
        assert signature is not None
        assert len(signature) == 64  # Ed25519 signatures are 64 bytes
        
        # Verify the signature
        result = crypto_manager.verify_signature(data, signature, identity.signing_public_key)
        assert result is True
    
    def test_verify_fails_with_tampered_data(self, crypto_manager, identity):
        """Test that verification fails when data is tampered"""
        original_data = b"Original message"
        tampered_data = b"Tampered message"
        
        # Sign original data
        signature = crypto_manager.sign_data(original_data, identity.signing_private_key)
        
        # Verify with tampered data should fail
        with pytest.raises(SignatureVerificationError):
            crypto_manager.verify_signature(tampered_data, signature, identity.signing_public_key)
    
    def test_verify_fails_with_wrong_signature(self, crypto_manager, identity):
        """Test that verification fails with incorrect signature"""
        data = b"Test message"
        wrong_signature = os.urandom(64)
        
        with pytest.raises(SignatureVerificationError):
            crypto_manager.verify_signature(data, wrong_signature, identity.signing_public_key)
    
    def test_verify_fails_with_wrong_public_key(self, crypto_manager):
        """Test that verification fails with wrong public key"""
        identity1 = crypto_manager.generate_identity()
        identity2 = crypto_manager.generate_identity()
        
        data = b"Test message"
        signature = crypto_manager.sign_data(data, identity1.signing_private_key)
        
        # Verify with different public key should fail
        with pytest.raises(SignatureVerificationError):
            crypto_manager.verify_signature(data, signature, identity2.signing_public_key)


class TestSealedBoxEncryption:
    """Tests for sealed box encryption (private messages)"""
    
    def test_encrypt_and_decrypt_message(self, crypto_manager, identity):
        """Test encryption and decryption round-trip"""
        plaintext = b"This is a secret message!"
        
        # Encrypt
        ciphertext = crypto_manager.encrypt_message(
            plaintext, 
            identity.encryption_public_key
        )
        
        assert ciphertext is not None
        assert len(ciphertext) > len(plaintext)  # Includes ephemeral key + tag
        assert ciphertext != plaintext
        
        # Decrypt
        decrypted = crypto_manager.decrypt_message(
            ciphertext, 
            identity.encryption_private_key
        )
        
        assert decrypted == plaintext
    
    def test_decrypt_fails_with_wrong_private_key(self, crypto_manager):
        """Test that decryption fails with wrong private key"""
        identity1 = crypto_manager.generate_identity()
        identity2 = crypto_manager.generate_identity()
        
        plaintext = b"Secret message"
        
        # Encrypt for identity1
        ciphertext = crypto_manager.encrypt_message(
            plaintext, 
            identity1.encryption_public_key
        )
        
        # Try to decrypt with identity2's key
        with pytest.raises(DecryptionError):
            crypto_manager.decrypt_message(
                ciphertext, 
                identity2.encryption_private_key
            )
    
    def test_decrypt_fails_with_tampered_ciphertext(self, crypto_manager, identity):
        """Test that decryption fails with tampered ciphertext"""
        plaintext = b"Secret message"
        
        ciphertext = crypto_manager.encrypt_message(
            plaintext, 
            identity.encryption_public_key
        )
        
        # Tamper with ciphertext
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF  # Flip bits in last byte
        
        with pytest.raises(DecryptionError):
            crypto_manager.decrypt_message(
                bytes(tampered), 
                identity.encryption_private_key
            )
    
    def test_encrypt_empty_message(self, crypto_manager, identity):
        """Test encryption of empty message"""
        plaintext = b""
        
        ciphertext = crypto_manager.encrypt_message(
            plaintext, 
            identity.encryption_public_key
        )
        
        decrypted = crypto_manager.decrypt_message(
            ciphertext, 
            identity.encryption_private_key
        )
        
        assert decrypted == plaintext


class TestSessionKeyDerivation:
    """Tests for ECDH session key derivation"""
    
    def test_derive_session_key(self, crypto_manager):
        """Test session key derivation produces 32-byte key"""
        from cryptography.hazmat.primitives.asymmetric import x25519
        
        # Generate ephemeral keypairs for both peers
        local_private = x25519.X25519PrivateKey.generate()
        local_public = local_private.public_key()
        
        remote_private = x25519.X25519PrivateKey.generate()
        remote_public = remote_private.public_key()
        
        # Derive session key from local perspective
        session_key_local = crypto_manager.derive_session_key(
            local_private, 
            remote_public
        )
        
        assert session_key_local is not None
        assert len(session_key_local) == 32
    
    def test_session_keys_match_on_both_sides(self, crypto_manager):
        """Test that both peers derive the same session key"""
        from cryptography.hazmat.primitives.asymmetric import x25519
        
        # Generate ephemeral keypairs
        local_private = x25519.X25519PrivateKey.generate()
        local_public = local_private.public_key()
        
        remote_private = x25519.X25519PrivateKey.generate()
        remote_public = remote_private.public_key()
        
        # Derive session key from both perspectives
        session_key_local = crypto_manager.derive_session_key(
            local_private, 
            remote_public
        )
        
        session_key_remote = crypto_manager.derive_session_key(
            remote_private, 
            local_public
        )
        
        assert session_key_local == session_key_remote


class TestAEADEncryption:
    """Tests for ChaCha20-Poly1305 AEAD encryption with session keys"""
    
    def test_encrypt_and_decrypt_with_session_key(self, crypto_manager):
        """Test AEAD encryption/decryption round-trip"""
        plaintext = b"Test message for AEAD"
        session_key = os.urandom(32)
        nonce = os.urandom(12)
        
        # Encrypt
        ciphertext = crypto_manager.encrypt_with_session_key(
            plaintext, 
            session_key, 
            nonce
        )
        
        assert ciphertext is not None
        assert len(ciphertext) > len(plaintext)  # Includes auth tag
        assert ciphertext != plaintext
        
        # Decrypt
        decrypted = crypto_manager.decrypt_with_session_key(
            ciphertext, 
            session_key, 
            nonce
        )
        
        assert decrypted == plaintext
    
    def test_decrypt_fails_with_wrong_session_key(self, crypto_manager):
        """Test that decryption fails with wrong session key"""
        plaintext = b"Test message"
        session_key = os.urandom(32)
        wrong_key = os.urandom(32)
        nonce = os.urandom(12)
        
        ciphertext = crypto_manager.encrypt_with_session_key(
            plaintext, 
            session_key, 
            nonce
        )
        
        with pytest.raises(DecryptionError):
            crypto_manager.decrypt_with_session_key(
                ciphertext, 
                wrong_key, 
                nonce
            )
    
    def test_decrypt_fails_with_wrong_nonce(self, crypto_manager):
        """Test that decryption fails with wrong nonce"""
        plaintext = b"Test message"
        session_key = os.urandom(32)
        nonce = os.urandom(12)
        wrong_nonce = os.urandom(12)
        
        ciphertext = crypto_manager.encrypt_with_session_key(
            plaintext, 
            session_key, 
            nonce
        )
        
        with pytest.raises(DecryptionError):
            crypto_manager.decrypt_with_session_key(
                ciphertext, 
                session_key, 
                wrong_nonce
            )
    
    def test_encrypt_fails_with_invalid_key_length(self, crypto_manager):
        """Test that encryption fails with invalid key length"""
        plaintext = b"Test message"
        invalid_key = os.urandom(16)  # Wrong length
        nonce = os.urandom(12)
        
        with pytest.raises(CryptoError):
            crypto_manager.encrypt_with_session_key(
                plaintext, 
                invalid_key, 
                nonce
            )
    
    def test_encrypt_fails_with_invalid_nonce_length(self, crypto_manager):
        """Test that encryption fails with invalid nonce length"""
        plaintext = b"Test message"
        session_key = os.urandom(32)
        invalid_nonce = os.urandom(8)  # Wrong length
        
        with pytest.raises(CryptoError):
            crypto_manager.encrypt_with_session_key(
                plaintext, 
                session_key, 
                invalid_nonce
            )
    
    def test_authentication_tag_verification(self, crypto_manager):
        """Test that authentication tag is verified"""
        plaintext = b"Test message"
        session_key = os.urandom(32)
        nonce = os.urandom(12)
        
        ciphertext = crypto_manager.encrypt_with_session_key(
            plaintext, 
            session_key, 
            nonce
        )
        
        # Tamper with ciphertext (corrupts auth tag)
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        
        with pytest.raises(DecryptionError):
            crypto_manager.decrypt_with_session_key(
                bytes(tampered), 
                session_key, 
                nonce
            )


class TestKeystoreOperations:
    """Tests for keystore save/load operations"""
    
    def test_save_and_load_keystore(self, crypto_manager, identity, temp_keystore_path):
        """Test saving and loading keystore with correct password"""
        password = "test_password_123"
        
        # Save keystore
        crypto_manager.save_keystore(identity, password, temp_keystore_path)
        
        assert temp_keystore_path.exists()
        
        # Load keystore
        loaded_identity = crypto_manager.load_keystore(password, temp_keystore_path)
        
        # Verify loaded identity matches original
        assert loaded_identity.peer_id == identity.peer_id
        assert loaded_identity.created_at == identity.created_at
        
        # Verify keys work correctly by signing and verifying
        test_data = b"Test data"
        signature = crypto_manager.sign_data(test_data, loaded_identity.signing_private_key)
        result = crypto_manager.verify_signature(test_data, signature, identity.signing_public_key)
        assert result is True
    
    def test_load_keystore_fails_with_wrong_password(
        self, 
        crypto_manager, 
        identity, 
        temp_keystore_path
    ):
        """Test that loading fails with incorrect password"""
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        
        # Save with correct password
        crypto_manager.save_keystore(identity, correct_password, temp_keystore_path)
        
        # Try to load with wrong password
        with pytest.raises(KeystoreError):
            crypto_manager.load_keystore(wrong_password, temp_keystore_path)
    
    def test_load_nonexistent_keystore_fails(self, crypto_manager):
        """Test that loading non-existent keystore fails"""
        nonexistent_path = Path("/nonexistent/path/keystore.enc")
        
        with pytest.raises(KeystoreError):
            crypto_manager.load_keystore("password", nonexistent_path)
    
    def test_keystore_file_format(self, crypto_manager, identity, temp_keystore_path):
        """Test that keystore file has expected format"""
        password = "test_password"
        
        crypto_manager.save_keystore(identity, password, temp_keystore_path)
        
        # Read raw file
        with open(temp_keystore_path, 'rb') as f:
            data = f.read()
        
        # Check minimum size (salt + nonce + some encrypted data)
        assert len(data) > 28  # 16 (salt) + 12 (nonce) + encrypted data
        
        # Verify we can extract salt and nonce
        salt = data[:16]
        nonce = data[16:28]
        ciphertext = data[28:]
        
        assert len(salt) == 16
        assert len(nonce) == 12
        assert len(ciphertext) > 0
    
    def test_export_and_import_identity(self, crypto_manager, identity, temp_keystore_path):
        """Test export and import functionality"""
        password = "export_password"
        
        # Export identity
        crypto_manager.export_identity(identity, password, temp_keystore_path)
        
        # Import identity
        imported_identity = crypto_manager.import_identity(password, temp_keystore_path)
        
        # Verify imported identity matches
        assert imported_identity.peer_id == identity.peer_id
        
        # Verify functionality
        test_data = b"Test export/import"
        signature = crypto_manager.sign_data(test_data, imported_identity.signing_private_key)
        result = crypto_manager.verify_signature(test_data, signature, identity.signing_public_key)
        assert result is True
    
    def test_keystore_with_empty_password(self, crypto_manager, identity, temp_keystore_path):
        """Test that keystore works with empty password (though not recommended)"""
        password = ""
        
        crypto_manager.save_keystore(identity, password, temp_keystore_path)
        loaded_identity = crypto_manager.load_keystore(password, temp_keystore_path)
        
        assert loaded_identity.peer_id == identity.peer_id
    
    def test_keystore_with_unicode_password(self, crypto_manager, identity, temp_keystore_path):
        """Test that keystore works with unicode password"""
        password = "пароль密码🔐"
        
        crypto_manager.save_keystore(identity, password, temp_keystore_path)
        loaded_identity = crypto_manager.load_keystore(password, temp_keystore_path)
        
        assert loaded_identity.peer_id == identity.peer_id


class TestEdgeCases:
    """Tests for edge cases and error conditions"""
    
    def test_sign_empty_data(self, crypto_manager, identity):
        """Test signing empty data"""
        data = b""
        signature = crypto_manager.sign_data(data, identity.signing_private_key)
        result = crypto_manager.verify_signature(data, signature, identity.signing_public_key)
        assert result is True
    
    def test_encrypt_large_message(self, crypto_manager, identity):
        """Test encryption of large message"""
        # 1 MB message
        plaintext = os.urandom(1024 * 1024)
        
        ciphertext = crypto_manager.encrypt_message(
            plaintext, 
            identity.encryption_public_key
        )
        
        decrypted = crypto_manager.decrypt_message(
            ciphertext, 
            identity.encryption_private_key
        )
        
        assert decrypted == plaintext
    
    def test_aead_with_large_message(self, crypto_manager):
        """Test AEAD encryption with large message"""
        plaintext = os.urandom(1024 * 1024)  # 1 MB
        session_key = os.urandom(32)
        nonce = os.urandom(12)
        
        ciphertext = crypto_manager.encrypt_with_session_key(
            plaintext, 
            session_key, 
            nonce
        )
        
        decrypted = crypto_manager.decrypt_with_session_key(
            ciphertext, 
            session_key, 
            nonce
        )
        
        assert decrypted == plaintext
