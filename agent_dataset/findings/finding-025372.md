---
id: 25372
severity: "Low/Info"
---

# Signatures in the SyrupRouter are not fully compatible with EIP712

## Description

EIP712 [defines](<https://eips.ethereum.org/EIPS/eip-712#eth_signtypeddata>) the digest as keccak256("\x19\x01" ‖ domainSeparator ‖ hashStruct(message)). domainSeparator [is](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/EIP712.sol#L88-L90>) keccak256(abi.encode(TYPE_HASH, _hashedName, _hashedVersion, block.chainid, address([this](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/EIP712.sol#L37-L38>)))).

TYPE_HASH [is](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/MessageHashUtils.sol#L76>) keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"); hashStruct(message)) is dependent on the application, ERC20Permit is a good [example](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC20Permit.sol>).

In this case it would be something like: ​ AUTH_TYPEHASH = keccak256("Auth(address lender,uint256 nonce,uint256 bitmap,uint256 deadline)");​ bytes32 structHash = keccak256(abi.encode(AUTH_TYPEHASH, msg.sender, nonces[msg.sender]++, bitmap, deadline);​

And the final digest is keccak256(abi.encodePacked("\x19\x01", domainSeparator, structHash).

## Proof of Concept

No PoC provided.

## Recommendation

To be strictly compliant, the structure above should be applied. However, signatures are signed by Maple so it has no impact on users.
