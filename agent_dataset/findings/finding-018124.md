---
id: 18124
severity: "High"
---

# TRANSFERING KIBToken TO YOURSELF INCREASES YOUR BALANCE

## Description

Using temporary variables to update balances is a dangerous construction.

If transferred to yourself, it will cause your balance to increase, thus growing the token balance infinitely.

## Proof of Concept

KIBToken overrides `_transfer()` to perform the transfer of the token, the code is as follows:

```solidity
function _transfer(address from, address to, uint256 amount) internal override {
    if (from == address(0)) {
        revert Errors.ERC20_TRANSFER_FROM_THE_ZERO_ADDRESS();
    }
    if (to == address(0)) {
        revert Errors.ERC20_TRANSER_TO_THE_ZERO_ADDRESS();
    }
    _refreshCumulativeYield();
    _refreshYield();

    uint256 startingFromBalance = this.balanceOf(from);
    if (startingFromBalance < amount) {
        revert Errors.ERC20_TRANSFER_AMOUNT_EXCEEDS_BALANCE();
    }
    uint256 newFromBalance = startingFromBalance - amount;
    uint256 newToBalance = this.balanceOf(to) + amount;

    uint256 previousEpochCumulativeYield_ = _previousEpochCumulativeYield;
    uint256 newFromBaseBalance = WadRayMath.wadToRay(newFromBalance).rayDiv(previousEpochCumulativeYield_);
    uint256 newToBaseBalance = WadRayMath.wadToRay(newToBalance).rayDiv(previousEpochCumulativeYield_);

    if (amount > 0) {
        _totalBaseSupply -= (_baseBalances[from] - newFromBaseBalance);
        _totalBaseSupply += (newToBaseBalance - _baseBalances[to]);
        _baseBalances[from] = newFromBaseBalance;
        _baseBalances[to] = newToBaseBalance;//<--------if from==to,this place Will overwrite the reduction above
    }

    emit Transfer(from, to, amount);
}
```

From the code above we can see that using temporary variables “newToBaseBalance” to update balances.

Using temporary variables is a dangerous construction.

If the from and to are the same, the balance[to] update will overwrite the balance[from] update.

To simplify the example:

Suppose: balance[alice]=10 , and execute transferFrom(from=alice,to=alice,5)

Define the temporary variable: temp_variable = balance[alice]=10

So update the steps as follows:

1. `balance[to=alice] = temp_variable - 5 =5`
2. `balance[from=alice] = temp_variable + 5 =15`

After Alice transferred it to herself, the balance was increased by 5.

The test code is as follows:

add to KIBToken.transfer.t.sol

```solidity
//test from == to
function test_transfer_same() public {
    _KIBToken.mint(_alice, 10 ether);
    assertEq(_KIBToken.balanceOf(_alice), 10 ether);
    vm.prank(_alice);
    _KIBToken.transfer(_alice, 5 ether);   //<-----alice transfer to alice 
    assertEq(_KIBToken.balanceOf(_alice), 15 ether); //<-----increases 5 eth
}

forge test --match test_transfer_same -vvv

Running 1 test for test/kuma-protocol/kib-token/KIBToken.transfer.t.sol:KIBTokenTransfer
[PASS] test_transfer_same() (gas: 184320)
Test result: ok. 1 passed; 0 failed; finished in 24.67ms
```

## Recommendation

A more general method is to use:

```solidity
balance[to]-=amount
balance[from]+=amount
```

In view of the complexity of the amount calculation, if the code is to be easier to read, it is recommended:

```solidity
function _transfer(address from, address to, uint256 amount) internal override {
    if (from == address(0)) {
        revert Errors.ERC20_TRANSFER_FROM_THE_ZERO_ADDRESS();
    }
    if (to == address(0)) {
        revert Errors.ERC20_TRANSER_TO_THE_ZERO_ADDRESS();
    }
    _refreshCumulativeYield();
    _refreshYield();

    if (from != to) {
        uint256 startingFromBalance = this.balanceOf(from);
        if (startingFromBalance < amount) {
            revert Errors.ERC20_TRANSFER_AMOUNT_EXCEEDS_BALANCE();
        }
        uint256 newFromBalance = startingFromBalance - amount;
        uint256 newToBalance = this.balanceOf(to) + amount;

        uint256 previousEpochCumulativeYield_ = _previousEpochCumulativeYield;
        uint256 newFromBaseBalance = WadRayMath.wadToRay(newFromBalance).rayDiv(previousEpochCumulativeYield_);
        uint256 newToBaseBalance = WadRayMath.wadToRay(newToBalance).rayDiv(previousEpochCumulativeYield_);

        if (amount > 0) {
            _totalBaseSupply -= (_baseBalances[from] - newFromBaseBalance);
            _totalBaseSupply += (newToBaseBalance - _baseBalances[to]);
            _baseBalances[from] = newFromBaseBalance;
            _baseBalances[to] = newToBaseBalance;
        }
    }
    emit Transfer(from, to, amount);
}
```

The Warden has shown a way to leverage a programming mistake to duplicate an account balances, because this breaks protocol invariants, I agree with High Severity.

We agree that this is a high risk issue and we intend to fix this.

<https://github.com/code-423n4/2023-02-kuma/pull/3>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a self‑transfer balance inflation bug that occurs when the token contract processes a transfer where the sender and recipient are the same address. The root cause is the use of temporary variables to compute the new balances and then applying the updates in a sequence that assumes the source and destination are distinct. When from and to are identical, the contract first writes the reduced balance to the destination slot and then overwrites it with the increased balance calculated from the same temporary value, effectively adding the transferred amount to the account instead of leaving it unchanged. An attacker can exploit this by calling the public transfer function with their own address as both parameters and any positive amount, causing their token balance to increase by that amount on each call. Because the function does not guard against self‑transfer, the inflation can be repeated arbitrarily, breaking the protocol’s accounting invariants, diluting token value, and potentially allowing the attacker to drain value from the system or manipulate governance. The issue manifests only when the transfer amount is greater than zero and the contract’s internal logic updates base balances using the temporary newToBaseBalance after having already adjusted the source balance, which is overwritten when the addresses match. All token holders and any downstream contracts that rely on the token’s supply integrity are affected. The bug was discovered during a formal audit when a test case transferred tokens from an address to itself and observed the balance growing from 10 to 15 units. It is easy to miss because self‑transfers are rarely exercised in normal usage and the code appears correct for distinct addresses, so the logical error is hidden behind a seemingly harmless conditional. The proper fix is to treat a self‑transfer as a no‑op, either by early‑returning when from equals to, or by updating balances using a direct subtraction and addition without intermediate temporary variables, ensuring that the reduction and addition are applied to separate storage slots. This aligns the implementation with the generic ERC‑20 invariant that a transfer does not change the total supply nor the sender’s balance when the sender and receiver are identical, and prevents the infinite balance growth class of bugs known as self‑transfer inflation or double‑counting errors.
