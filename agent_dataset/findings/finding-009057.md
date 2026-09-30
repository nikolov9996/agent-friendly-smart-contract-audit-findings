---
id: 9057
severity: "High"
---

# StakedToken holders can circumvent restriction by approving another address to withdraw

## Description

StakedTokens come with transfer restricted functionality. Given that withdraw burns tokens, a path to circumventing the transfer restriction exists.
First, the _withdraw function checks that the caller is not restricted but not the owner or receiver. The caller in the exploit scenario may be an address that has no StakedTokens and therefore has not been restricted.
```solidity
function _withdraw(address caller, address receiver, address owner, uint256 assets, uint256 shares)
internal
override
{
    _checkActionRestriction(caller);
    return ERC4626._withdraw(caller, receiver, owner, assets, shares);
}
```
Then on the _update the _from restriction check is ignored when minting or burning.
```solidity
function _update(address _from, address _to, uint256 _value) internal override {
    if (_from != address(0) && _to != address(0)) {
        // check action restrictions if the transfer is not a burn nor a mint
        _checkActionRestriction(_from);
    }
    return ERC20._update(_from, _to, _value);
}
```

## Proof of Concept

```solidity
function testRestrictionCircumvention() public {
    address anyAddress = makeAddr("anyAddress");
    vm.startPrank(alice);
    siusd.approve(anyAddress, 1000e18);
    vm.expectRevert(abi.encodeWithSelector(ActionRestriction.ActionRestricted.selector, alice,
    block.timestamp + 1));
    siusd.withdraw(1000e18, alice, alice);
    vm.stopPrank();
    vm.prank(anyAddress);
    siusd.withdraw(1000e18, alice, alice);
    assertEq(siusd.balanceOf(address(alice)), 0e18);
    assertEq(iusd.balanceOf(address(alice)), 1000e18);
}
```

## Recommendation

Ensure the owner address argument is also validated to not be restricted.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a bypass of the transfer‑restriction mechanism built into a StakedToken that is intended to prevent certain accounts from moving their shares. The contract enforces the restriction only on the address that directly calls the withdraw function, checking the caller with _checkActionRestriction(caller). However, the withdraw operation internally burns the caller’s shares and transfers the underlying assets, and the ERC20 _update hook that would normally enforce the restriction on the token holder is written to skip the check when either the source or destination address is the zero address (the case for minting or burning). Consequently, a restricted holder can approve an unrestricted third party to call withdraw on their behalf; the third party is not restricted, so the initial caller check passes, and the subsequent _update call does not enforce the restriction because the burn uses address(0) as the destination. An attacker can therefore move tokens that should be locked, violating the protocol’s accounting assumptions that restricted accounts cannot transfer or withdraw assets. From a user’s perspective the expected behavior – that a restricted account’s balance remains immobile – is broken; the user may see their tokens disappear from the restricted address and appear in another address without any explicit action. The issue was discovered during a security audit when a test case demonstrated that after approving a different address, the withdraw call succeeded and the restricted holder’s balance became zero while the underlying token balance increased. The bug is subtle because the restriction logic appears to be present and is exercised for normal transfers, so developers may assume it also protects burns. To remediate, the contract should also validate that the owner (the address whose shares are being burned) is not restricted, or the _update hook should enforce the restriction even for burn operations, ensuring that any action that changes a restricted holder’s balance is blocked. This class of bug falls under improper access control where a security check is omitted for a specific code path, leading to an unintended privilege escalation and potential loss of locked funds.
