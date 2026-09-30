---
id: 23270
severity: "Critical"
---

# SignatureValidator::setAllowlist is unrestricted leading to free purchases of tokens

## Description

SignatureValidator::setAllowlist is unrestricted.  
Since SignatureValidator inherited by ReferralManager and TokenBank this has downstream consequences.  
For TokenBank in particular this means that  

- attacker can call TokenBank::setAllowlist(maliciousAllowList) where maliciousAllowList::isSigner just returns true for the attacker  
- They can then spoof a signature by a Remora admin  
- call TokenBank::buyTokenOCP using the spoofed signature  
- buyTokenOCP indirectly calls _buyToken with useStableCoin == false  
- thus the entire code path guarded by `if (useStablecoin) {` is skipped and no stablecoins are transferred from the attacker  

The same vulnerability could be used to steal all of ReferralManager's bonuses.  

**Impact:** Attacker can  

- purchase all remaining central tokens for free  
- steal from ReferralManager bonuses

## Proof of Concept

Add `MaliciousAllowlist.sol`

```solidity
contract MaliciousAllowlist {
    address maliciousSigner;
    constructor(address _maliciousSigner) {
        maliciousSigner = _maliciousSigner;
    }
    function isSigner(address signer) public view returns (bool) {
        return (signer == maliciousSigner);
    }
}
```

And then add this test to `TokenBankTest.t.sol` (after adding import of `MaliciousSigner`)

```solidity
function test_cyfrin_buyTokenOCP_for_free() public {
    uint64 TOTAL_TOKENS = 10_000;
    _addCentralToTokenBank(60e6, true, 50_000);
    centralTokenProxy.mint(address(tokenBankProxy), uint64(TOTAL_TOKENS));
    address attacker = getDomesticUser(2);
    (address attackerSigner, uint256 sk) = makeAddrAndKey("BUY_SIGNER");
    /*
    * Attacker sets a malicious Allowlist and signs the buy instead of a Remora Admin
    */
    vm.startPrank(attackerSigner);
    MaliciousAllowlist maliciousAllowlist = new MaliciousAllowlist(attackerSigner);
    tokenBankProxy.setAllowlist(address(maliciousAllowlist));
    bytes32 typeHash = keccak256("BuyToken(address investor, address token, uint256 amount)");
    bytes32 structHash = keccak256(abi.encode(typeHash, attacker, address(centralTokenProxy),
    uint256(TOTAL_TOKENS)));
    bytes32 digest = MessageHashUtils.toTypedDataHash(tokenBankProxy.getDomainSeparator(),
    structHash);
    (uint8 v, bytes32 r, bytes32 s) = vm.sign(sk, digest);
    bytes memory sig = abi.encodePacked(r, s, v);
    vm.stopPrank();
    /*
    * Now attacker buys all the tokens using the signature they created
    */
    vm.prank(attacker);
    tokenBankProxy.buyTokenOCP(attackerSigner, address(centralTokenProxy), TOTAL_TOKENS, sig);
    // attacker receives domestic child tokens
    assertEq(d_childTokenProxy.balanceOf(attacker), TOTAL_TOKENS);
}
```

## Recommendation

Since SignatureValidator is an abstract contract, setAllowlist should be an internal function.  

```solidity
- function setAllowlist(address allowlist) external {
+ function _setAllowlist(address allowlist) internal {
    if (allowlist == address(0)) revert InvalidAddress();
    SVStorage storage $ = _getSVStorageStorage();
    if ($._allowlist != allowlist) {
        $._allowlist = allowlist;
        emit AllowlistSet(allowlist);
    }
}
```

TokenBank should then expose setAllowlist as an external function with the restricted modifier  

```solidity
+ function setAllowlist(address signer) external restricted {
+     super._setAllowlist(signer);
+ }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unrestricted public function that sets the address of the signature allowlist contract, which is inherited by both the token bank and the referral manager. Because the function lacks any access control, any user can call it and replace the legitimate allowlist with a malicious contract that always returns true for the isSigner query. When an attacker points the token bank to such a malicious allowlist, they can craft a signature that appears to be signed by a privileged admin, bypass the signature verification, and invoke the token purchase function with the stablecoin flag set to false. This causes the execution path that would normally transfer stablecoins from the buyer to be skipped, resulting in the contract minting the requested central tokens to the attacker without any payment. The same flaw can be leveraged in the referral manager to approve any signer, allowing the attacker to claim all referral bonuses. The impact is that an attacker can acquire all remaining central tokens for free and drain referral rewards, effectively stealing value from the protocol. The issue occurs whenever the setAllowlist function is called, which can happen at any time because it is public, and it is triggered when the attacker subsequently calls the purchase or referral functions. Users are affected because they may see tokens appear in their wallet without having transferred funds, while the protocol loses assets. The flaw was discovered during a security audit that examined inheritance and access control, and it is subtle because the function appears innocuous and the signature verification logic seems sound when the allowlist is correct. The bug belongs to the class of “unrestricted configuration setter” or “access control bypass” vulnerabilities, where a critical contract reference can be overwritten by an attacker. From a user perspective the symptom is receiving tokens for free or seeing referral rewards disappear, contrary to the expectation that a purchase requires payment. To remediate, the setter should be made internal and only exposed through a restricted external function callable by authorized roles, ensuring that only trusted parties can change the allowlist and preserving the integrity of signature verification.
