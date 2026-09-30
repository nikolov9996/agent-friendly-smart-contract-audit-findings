---
id: 16103
severity: "High"
---

# AML requirement checks skipped if no AML attribute for user

## Description

The _isExpired function returns false when attribute.epoch == 0 which happens when the attribute is missing and was not set by any Quadrata issuer.
```solidity
/// Checks if an attribute is expired.
function _isExpired(
    IQuadPassportStore.Attribute memory attribute,
    uint256 maxAttributeAge
)
    internal
    view
    returns (bool)
{
    return attribute.epoch > 0 && attribute.epoch < block.timestamp - maxAttributeAge;
}
```
The AML check is implemented as
```solidity
// Check: AML risk score.
if (
    !amlAttribute.value.amlLessThanEqual(requirements.maxAMLRiskScore)
    || _isExpired(amlAttribute, maxAllowedAttributeAge)
) {
    revert AMLCheckFailed(deal, account);
}
```
For a non-existent AML attribute, all amlAttribute values will be zero and the revert is never reached.
If a deal requires an AML score of 5 or below and the investor has not performed KYC/AML checks they will still be able to invest in the deal.

## Proof of Concept

no poc

## Recommendation

If any Quadrata attribute is missing but a requirement exists for the Deal, the verifyEligibility function should revert. Consider treating a null attribute (attribute.epoch == 0) as expired:
```solidity
/// Checks if an attribute is expired.
- function _isExpired(
+ function _isExpiredOrNull(
    IQuadPassportStore.Attribute memory attribute,
    uint256 maxAttributeAge
)
    internal
    view
    returns (bool)
{
    -
    return attribute.epoch > 0 && attribute.epoch < block.timestamp - maxAttributeAge;
    +
    return attribute.epoch == 0 || attribute.epoch < block.timestamp - maxAttributeAge;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logic flaw in the AML eligibility verification where a missing AML attribute is treated as a valid, non‑expired attribute, allowing investors who have never completed KYC/AML to satisfy a deal’s AML requirement. The root cause is the _isExpired helper returning false when attribute.epoch equals 0; the function only checks that epoch > 0 before comparing to the allowed age, so a null attribute (epoch == 0) is considered not expired. The AML check combines a risk‑score comparison with the _isExpired result, and because both sub‑conditions evaluate to false for a zeroed attribute, the require statement never reverts. An attacker can simply call the investment function without having any AML attribute stored by a Quadrata issuer and still pass the check, thereby investing in deals that explicitly require an AML risk score of 5 or lower. The impact is that the protocol can admit non‑compliant participants, breaking regulatory assumptions, exposing the platform to money‑laundering risk, and potentially causing legal or reputational damage. This condition occurs whenever a user’s AML attribute has never been set (epoch == 0), which is common for new users or for assets that do not enforce mandatory KYC at onboarding. The affected parties include the protocol’s compliance team, investors who expect only verified participants, and any deal that relies on the AML guard. The issue was discovered during a security audit that examined the verifyEligibility function and noticed that the revert path was never reached for zeroed attributes, a subtle bug because the code appears to perform a check but silently accepts default values. It is hard to notice because the contract does not emit an error or warning; the transaction simply succeeds, giving the impression that the user is compliant. To remediate, the _isExpired function should treat a null attribute as expired (for example return attribute.epoch == 0 || attribute.epoch < block.timestamp - maxAttributeAge) or the eligibility logic should explicitly revert when an expected attribute is missing. This change restores the intended business rule that a user without a recorded AML score must be rejected, aligning the contract’s behavior with regulatory expectations and preventing funds from being allocated to unverified participants.
