"""
Cryptography Manager for P2P Encrypted BBS

Handles all cryptographic operations including:
- Identity generation (Ed25519 signing + X25519 encryption keypairs)
- Message signing and verification
- Encryption and decryption (sealed box and session-based AEAD)
- Keystore management with password protection
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend


@dataclass
class Identity:
    """
    User identity containing signing and encryption keypairs.
    
    Attributes:
        signing_private_key: Ed25519 private key for signing messages
        signing_public_key: Ed25519 public key for signature verification
        encryption_private_key: X25519 private key for decryption
        encryption_public_key: X25519 public key for encryption
        peer_id: Unique identifier derived from signing public key
        created_at: Timestamp of identity creation
    """
    signing_private_key: ed25519.Ed25519PrivateKey
    signing_public_key: ed25519.Ed25519PublicKey
    encryption_private_key: x25519.X25519PrivateKey
    encryption_public_key: x25519.X25519PublicKey
    peer_id: str
    created_at: datetime


class CryptoError(Exception):
    """Base exception for cryptographic errors"""
    pass


class SignatureVerificationError(CryptoError):
    """Raised when signature verification fails"""
    pass


class DecryptionError(CryptoError):
    """Raised when decryption fails"""
    pass


class KeystoreError(CryptoError):
    """Raised when keystore operations fail"""
    pass


class CryptoManager:
    """
    Manages all cryptographic operations for the BBS application.
    """
    
    def __init__(self):
        self.backend = default_backend()
    
    def generate_identity(self) -> Identity:
        """
        Generate a new cryptographic identity with Ed25519 signing keypair
        and X25519 encryption keypair.
        
        Returns:
            Identity: New identity with generated keypairs and derived peer_id
        """
        # Generate Ed25519 signing keypair
        signing_private_key = ed25519.Ed25519PrivateKey.generate()
        signing_public_key = signing_private_key.public_key()
        
        # Generate X25519 encryption keypair
        encryption_private_key = x25519.X25519PrivateKey.generate()
        encryption_public_key = encryption_private_key.public_key()
        
        # Derive peer_id from signing public key using SHA-256
        peer_id = self._derive_peer_id(signing_public_key)
        
        return Identity(
            signing_private_key=signing_private_key,
            signing_public_key=signing_public_key,
            encryption_private_key=encryption_private_key,
            encryption_public_key=encryption_public_key,
            peer_id=peer_id,
            created_at=datetime.utcnow()
        )
    
    def _derive_peer_id(self, public_key: ed25519.Ed25519PublicKey) -> str:
        """
        Derive a unique peer identifier from an Ed25519 public key using SHA-256.
        
        Args:
            public_key: Ed25519 public key
            
        Returns:
            str: Hex-encoded SHA-256 hash of the public key
        """
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        hash_digest = hashlib.sha256(public_key_bytes).digest()
        return hash_digest.hex()

    def sign_data(self, data: bytes, private_key: ed25519.Ed25519PrivateKey) -> bytes:
        """
        Sign data using Ed25519 private key.
        
        Args:
            data: Data to sign
            private_key: Ed25519 private key for signing
            
        Returns:
            bytes: Signature (64 bytes)
            
        Raises:
            CryptoError: If signing fails
        """
        try:
            signature = private_key.sign(data)
            return signature
        except Exception as e:
            raise CryptoError(f"Failed to sign data: {e}")
    
    def verify_signature(
        self, 
        data: bytes, 
        signature: bytes, 
        public_key: ed25519.Ed25519PublicKey
    ) -> bool:
        """
        Verify Ed25519 signature on data.
        
        Args:
            data: Original data that was signed
            signature: Signature to verify
            public_key: Ed25519 public key for verification
            
        Returns:
            bool: True if signature is valid
            
        Raises:
            SignatureVerificationError: If signature is invalid
        """
        try:
            public_key.verify(signature, data)
            return True
        except Exception as e:
            raise SignatureVerificationError(f"Signature verification failed: {e}")

    def encrypt_message(
        self, 
        plaintext: bytes, 
        recipient_public_key: x25519.X25519PublicKey
    ) -> bytes:
        """
        Encrypt a message using X25519 sealed box encryption for private messages.
        
        This implements a sealed box where the sender's identity is anonymous.
        The ciphertext includes an ephemeral public key.
        
        Args:
            plaintext: Message to encrypt
            recipient_public_key: Recipient's X25519 public key
            
        Returns:
            bytes: Encrypted message (ephemeral_public_key + ciphertext + tag)
            
        Raises:
            CryptoError: If encryption fails
        """
        try:
            # Generate ephemeral keypair for this message
            ephemeral_private_key = x25519.X25519PrivateKey.generate()
            ephemeral_public_key = ephemeral_private_key.public_key()
            
            # Derive shared secret using ECDH
            shared_secret = ephemeral_private_key.exchange(recipient_public_key)
            
            # Derive encryption key using HKDF
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'sealed_box_encryption',
                backend=self.backend
            )
            encryption_key = hkdf.derive(shared_secret)
            
            # Encrypt with ChaCha20-Poly1305
            cipher = ChaCha20Poly1305(encryption_key)
            nonce = b'\x00' * 12  # Sealed box uses zero nonce (one-time key)
            ciphertext = cipher.encrypt(nonce, plaintext, None)
            
            # Return ephemeral public key + ciphertext
            ephemeral_public_key_bytes = ephemeral_public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            return ephemeral_public_key_bytes + ciphertext
            
        except Exception as e:
            raise CryptoError(f"Failed to encrypt message: {e}")
    
    def decrypt_message(
        self, 
        ciphertext: bytes, 
        private_key: x25519.X25519PrivateKey
    ) -> bytes:
        """
        Decrypt a sealed box encrypted message.
        
        Args:
            ciphertext: Encrypted message (ephemeral_public_key + ciphertext + tag)
            private_key: Recipient's X25519 private key
            
        Returns:
            bytes: Decrypted plaintext
            
        Raises:
            DecryptionError: If decryption fails
        """
        try:
            # Extract ephemeral public key (first 32 bytes)
            ephemeral_public_key_bytes = ciphertext[:32]
            encrypted_data = ciphertext[32:]
            
            # Reconstruct ephemeral public key
            ephemeral_public_key = x25519.X25519PublicKey.from_public_bytes(
                ephemeral_public_key_bytes
            )
            
            # Derive shared secret using ECDH
            shared_secret = private_key.exchange(ephemeral_public_key)
            
            # Derive decryption key using HKDF
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'sealed_box_encryption',
                backend=self.backend
            )
            decryption_key = hkdf.derive(shared_secret)
            
            # Decrypt with ChaCha20-Poly1305
            cipher = ChaCha20Poly1305(decryption_key)
            nonce = b'\x00' * 12
            plaintext = cipher.decrypt(nonce, encrypted_data, None)
            
            return plaintext
            
        except Exception as e:
            raise DecryptionError(f"Failed to decrypt message: {e}")
    
    def derive_session_key(
        self, 
        local_private_key: x25519.X25519PrivateKey,
        remote_public_key: x25519.X25519PublicKey
    ) -> bytes:
        """
        Derive a session key using ECDH and HKDF for peer-to-peer communication.
        
        Args:
            local_private_key: Local ephemeral X25519 private key
            remote_public_key: Remote ephemeral X25519 public key
            
        Returns:
            bytes: 32-byte session key for AEAD encryption
            
        Raises:
            CryptoError: If key derivation fails
        """
        try:
            # Perform ECDH key exchange
            shared_secret = local_private_key.exchange(remote_public_key)
            
            # Derive session key using HKDF
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'session_key_derivation',
                backend=self.backend
            )
            session_key = hkdf.derive(shared_secret)
            
            return session_key
            
        except Exception as e:
            raise CryptoError(f"Failed to derive session key: {e}")
    
    def encrypt_with_session_key(
        self, 
        plaintext: bytes, 
        session_key: bytes, 
        nonce: bytes
    ) -> bytes:
        """
        Encrypt data using ChaCha20-Poly1305 AEAD with a session key.
        
        Args:
            plaintext: Data to encrypt
            session_key: 32-byte session key
            nonce: 12-byte nonce (must be unique for each message)
            
        Returns:
            bytes: Ciphertext with authentication tag
            
        Raises:
            CryptoError: If encryption fails
        """
        try:
            if len(session_key) != 32:
                raise CryptoError("Session key must be 32 bytes")
            if len(nonce) != 12:
                raise CryptoError("Nonce must be 12 bytes")
            
            cipher = ChaCha20Poly1305(session_key)
            ciphertext = cipher.encrypt(nonce, plaintext, None)
            return ciphertext
            
        except Exception as e:
            raise CryptoError(f"Failed to encrypt with session key: {e}")
    
    def decrypt_with_session_key(
        self, 
        ciphertext: bytes, 
        session_key: bytes, 
        nonce: bytes
    ) -> bytes:
        """
        Decrypt data using ChaCha20-Poly1305 AEAD with a session key.
        
        Args:
            ciphertext: Encrypted data with authentication tag
            session_key: 32-byte session key
            nonce: 12-byte nonce (same as used for encryption)
            
        Returns:
            bytes: Decrypted plaintext
            
        Raises:
            DecryptionError: If decryption or authentication fails
        """
        try:
            if len(session_key) != 32:
                raise DecryptionError("Session key must be 32 bytes")
            if len(nonce) != 12:
                raise DecryptionError("Nonce must be 12 bytes")
            
            cipher = ChaCha20Poly1305(session_key)
            plaintext = cipher.decrypt(nonce, ciphertext, None)
            return plaintext
            
        except Exception as e:
            raise DecryptionError(f"Failed to decrypt with session key: {e}")

    def save_keystore(
        self, 
        identity: Identity, 
        password: str, 
        path: Path
    ) -> None:
        """
        Save identity to an encrypted keystore file using Argon2id and AES-GCM.
        
        The keystore format:
        - Salt (16 bytes)
        - Nonce (12 bytes)
        - Encrypted data (variable length)
        - Authentication tag (16 bytes, included in encrypted data)
        
        Args:
            identity: Identity to save
            password: Password for encryption
            path: Path to save keystore file
            
        Raises:
            KeystoreError: If saving fails
        """
        try:
            # Generate random salt for key derivation
            import os
            salt = os.urandom(16)
            
            # Derive encryption key from password using Scrypt
            # (Using Scrypt instead of Argon2id as it's more widely available)
            kdf = Scrypt(
                salt=salt,
                length=32,
                n=2**14,  # CPU/memory cost parameter
                r=8,      # Block size
                p=1,      # Parallelization parameter
                backend=self.backend
            )
            encryption_key = kdf.derive(password.encode('utf-8'))
            
            # Serialize identity to JSON
            identity_data = {
                'signing_private_key': identity.signing_private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                ).hex(),
                'signing_public_key': identity.signing_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                ).hex(),
                'encryption_private_key': identity.encryption_private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                ).hex(),
                'encryption_public_key': identity.encryption_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                ).hex(),
                'peer_id': identity.peer_id,
                'created_at': identity.created_at.isoformat()
            }
            plaintext = json.dumps(identity_data).encode('utf-8')
            
            # Encrypt with ChaCha20-Poly1305
            nonce = os.urandom(12)
            cipher = ChaCha20Poly1305(encryption_key)
            ciphertext = cipher.encrypt(nonce, plaintext, None)
            
            # Write to file: salt + nonce + ciphertext
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'wb') as f:
                f.write(salt)
                f.write(nonce)
                f.write(ciphertext)
                
        except Exception as e:
            raise KeystoreError(f"Failed to save keystore: {e}")
    
    def load_keystore(
        self, 
        password: str, 
        path: Path
    ) -> Identity:
        """
        Load identity from an encrypted keystore file.
        
        Args:
            password: Password for decryption
            path: Path to keystore file
            
        Returns:
            Identity: Loaded identity
            
        Raises:
            KeystoreError: If loading or decryption fails
        """
        try:
            # Read keystore file
            with open(path, 'rb') as f:
                salt = f.read(16)
                nonce = f.read(12)
                ciphertext = f.read()
            
            # Derive decryption key from password
            kdf = Scrypt(
                salt=salt,
                length=32,
                n=2**14,
                r=8,
                p=1,
                backend=self.backend
            )
            decryption_key = kdf.derive(password.encode('utf-8'))
            
            # Decrypt
            cipher = ChaCha20Poly1305(decryption_key)
            plaintext = cipher.decrypt(nonce, ciphertext, None)
            
            # Deserialize identity
            identity_data = json.loads(plaintext.decode('utf-8'))
            
            # Reconstruct keypairs
            signing_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(identity_data['signing_private_key'])
            )
            signing_public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(identity_data['signing_public_key'])
            )
            encryption_private_key = x25519.X25519PrivateKey.from_private_bytes(
                bytes.fromhex(identity_data['encryption_private_key'])
            )
            encryption_public_key = x25519.X25519PublicKey.from_public_bytes(
                bytes.fromhex(identity_data['encryption_public_key'])
            )
            
            return Identity(
                signing_private_key=signing_private_key,
                signing_public_key=signing_public_key,
                encryption_private_key=encryption_private_key,
                encryption_public_key=encryption_public_key,
                peer_id=identity_data['peer_id'],
                created_at=datetime.fromisoformat(identity_data['created_at'])
            )
            
        except FileNotFoundError:
            raise KeystoreError(f"Keystore file not found: {path}")
        except Exception as e:
            raise KeystoreError(f"Failed to load keystore: {e}")
    
    def export_identity(
        self, 
        identity: Identity, 
        password: str, 
        export_path: Path
    ) -> None:
        """
        Export identity to a backup file (same format as keystore).
        
        Args:
            identity: Identity to export
            password: Password for encryption
            export_path: Path to export file
            
        Raises:
            KeystoreError: If export fails
        """
        self.save_keystore(identity, password, export_path)
    
    def import_identity(
        self, 
        password: str, 
        import_path: Path
    ) -> Identity:
        """
        Import identity from a backup file.
        
        Args:
            password: Password for decryption
            import_path: Path to import file
            
        Returns:
            Identity: Imported identity
            
        Raises:
            KeystoreError: If import fails
        """
        return self.load_keystore(password, import_path)
