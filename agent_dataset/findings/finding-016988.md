---
id: 16988
severity: "High"
---

# Transfering funds to yourself increases your balance

## Description

```solidity
function _transfer(
    address _from,
    address _to,
    uint256 _id,
    uint256 _amount
) internal virtual {
    uint256 _fromBalance = _balances[_id][_from];
    ...
    uint256 _toBalance = _balances[_id][_to];

    unchecked {
        _balances[_id][_from] = _fromBalance - _amount;
        _balances[_id][_to] = _toBalance + _amount; // @audit : if _from == _to : rekt
    }
    ..
}
```
Furthermore, the `safeTransferFrom` function has the `checkApproval` modifier which passes without any limit if `_owner == _spender`:
```solidity
modifier checkApproval(address _from, address _spender) {
    if (!_isApprovedForAll(_from, _spender)) revert LBToken__SpenderNotApproved(_from, _spender);
    _;
}

function safeTransferFrom(
) public virtual override checkAddresses(_from, _to) checkApproval(_from, msg.sender) {

function _isApprovedForAll(address _owner, address _spender) internal view virtual returns (bool) {
    return _owner == _spender || _spenderApprovals[_owner][_spender];
}
```

## Proof of Concept

Add the following test to `LBToken.t.sol` (run it with `forge test --match-path test/LBToken.t.sol --match-test testSafeTransferFromOneself -vvvv`):
```solidity
function testSafeTransferFromOneself() public {
    uint256 amountIn = 1e18;

    (uint256[] memory _ids, , , ) = addLiquidity(amountIn, ID_ONE, 5, 0);

    uint256 initialBalance = pair.balanceOf(DEV, _ids[0]);

    assertEq(initialBalance, 333333333333333333); // using hardcoded value to ease understanding

    pair.safeTransferFrom(DEV, DEV, _ids[0], initialBalance); //transfering to oneself
    uint256 rektBalance1 = pair.balanceOf(DEV, _ids[0]); //computing new balance
    assertEq(rektBalance1, 2 * initialBalance); // the new balance is twice the initial one
    assertEq(rektBalance1, 666666666666666666); // using hardcoded value to ease understanding
}
```
As we can see here, this test checks that transfering all your funds to yourself doubles your balance, and it’s passing. This can be repeated again and again to increase your balance.

## Recommendation

* Add checks to make sure that `_from != _to` because that shouldn’t be useful anyway
  * Prefer the following:
```solidity
unchecked {
    _balances[_id][_from] -= _amount;
    _balances[_id][_to] += _amount;
}
```
The Warden has shown how, due to the improper usage of a supporting temporary variable, balance duplication can be achieved.

Mitigation will require ensuring that the intended variable is changed in storage, and the code offered by the warden should help produce a test case to compare the fix against.

Because the finding pertains to duplication of balances, causing a loss for users, I agree with High Severity.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the internal token transfer routine of the LBToken contract, where the function that moves a token amount from one address to another does not prevent the sender and receiver from being the same address. The routine reads the sender's balance into a temporary variable, subtracts the transfer amount, and then adds the same amount to the recipient's balance using an unchecked arithmetic block. Because the code does not check that the source (_from) and destination (_to) differ, a caller can invoke safeTransferFrom with identical addresses. The approval modifier further enables this by treating owner‑as‑spender as automatically approved, so the call passes without additional permission checks. When the same address is used for both parties, the subtraction and addition operate on the same storage slot, effectively performing a no‑op subtraction followed by an addition that doubles the stored balance. This creates a balance duplication effect: the user's token balance is multiplied by two each time the self‑transfer is executed, and the process can be repeated arbitrarily to inflate the balance without any collateral. From a user perspective, the symptoms are surprising – after initiating what appears to be a harmless transfer of all tokens to oneself, the UI may show that the balance has suddenly doubled, contradicting the expectation that the balance should remain unchanged. The impact is severe: an attacker can generate unlimited tokens for themselves, undermining the token's scarcity, breaking accounting invariants, and potentially draining value from liquidity pools or other protocol mechanisms that rely on accurate token accounting. The flaw was discovered during a formal audit by Code4rena, where a test case demonstrated that calling safeTransferFrom with identical from and to addresses caused the balance to double, confirming the duplication. The issue can be difficult to notice because the transaction does not revert and appears to succeed, while the underlying state change is subtle – a simple arithmetic increase without any explicit error. Conceptually, the bug belongs to the class of “self‑transfer balance duplication” or “unchecked self‑transfer arithmetic” vulnerabilities, where missing invariants allow a contract to modify its own balance in a way that violates business logic. To remediate, the transfer logic should enforce a strict inequality between sender and receiver, rejecting any attempt to transfer to oneself, or restructure the unchecked block to use direct subtraction and addition on storage values without temporary variables that can be reused for the same address. Adding the explicit check prevents the duplication path, restores correct accounting, and aligns the contract with the intended token economics.
