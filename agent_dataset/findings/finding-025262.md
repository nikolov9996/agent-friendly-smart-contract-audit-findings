---
id: 25262
severity: "Crit/High"
---

# Credentials can be manipulated

## Description

KeyringCoreV2::createCredential() downcasts several variables, uint24(policyId), uint32(epoch), uint32(epochExp), uint168(cost) when sending them to RsaVerifyOptimized::verifyAuthMessage(), where they are encoded to a signature.

Downcasting does not revert so if a key signs a message with a certain variable smaller than the casting that is being made, attackers can send this variable but with higher upper bits set to 1, such that the encoded message is still the same but the variable that is sent to KeyringCoreV2Base::_createCredential() is actually much bigger.

One example of an abuse is an attacker setting a much bigger epochExp, which is downcasted to the much lower value to sign, but sets the expiry of its _entityData[policyId][tradingAddress].exp to a value very far away in the future (up to uint64).

Another example is an attacker setting epoch to a much larger value such that it can set the credentials forever.

## Proof of Concept

No PoC provided.

## Recommendation

All the downcastings in the codebase should use the safe casting lib from [OpenZeppelin](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/math/SafeCast.sol>).

Additionally, signatures could implement a nonce system to complement the deadline epoch argument.
