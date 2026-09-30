---
id: 14951
severity: "High"
---

# GolomTrader’s `_settleBalances` double counts protocol fee, reducing taker’s payout for a NFT sold

## Description

Currently `((o.totalAmt * 50) / 10000)` protocol fee share is multiplied by `amount` twice when being accounted for as a deduction from the total in amount due to the `msg.sender` taker calculations in _settleBalances(), which is called by fillBid() and fillCriteriaBid() to handle the payouts.

Setting the severity to be high as reduced payouts is a fund loss impact for taker, which receives less than it’s due whenever `amount > 1`.

Notice that the amount lost to the taker is left on the contract balance and currently is subject to other vulnerabilities, i.e. can be easily stolen by an attacker that knowns these specifics and tracks contract state. When these issues be fixed this amount to be permanently frozen on the GolomTrader’s balance as it’s unaccounted for in all subsequent calculations (i.e. all the transfers are done with regard to the accounts recorded, this extra sum is unaccounted, there is no general native funds rescue function, so when all other mechanics be fixed the impact will be permanent freeze of the part of taker’s funds).

## Proof of Concept

_settleBalances() uses `(o.totalAmt - protocolfee - ...) * amount`, which is `o.totalAmt * amount - ((o.totalAmt * 50) / 10000) * amount * amount - ...`, counting protocol fee extra `amount - 1` times:
```solidity
payEther(
    (o.totalAmt - protocolfee - o.exchange.paymentAmt - o.prePayment.paymentAmt - o.refererrAmt) *
        amount -
        p.paymentAmt,
    msg.sender
);
} else {
    payEther(
        (o.totalAmt - protocolfee - o.exchange.paymentAmt - o.prePayment.paymentAmt) * amount - p.paymentAmt,
        msg.sender
    );
```

```solidity
function _settleBalances(
    Order calldata o,
    uint256 amount,
    address referrer,
    Payment calldata p
) internal {
    uint256 protocolfee = ((o.totalAmt * 50) / 10000) * amount;
    WETH.transferFrom(o.signer, address(this), o.totalAmt * amount);
    WETH.withdraw(o.totalAmt * amount);
    payEther(protocolfee, address(distributor));
    payEther(o.exchange.paymentAmt * amount, o.exchange.paymentAddress);
    payEther(o.prePayment.paymentAmt * amount, o.prePayment.paymentAddress);
    if (o.refererrAmt > 0 && referrer != address(0)) {
        payEther(o.refererrAmt * amount, referrer);
        payEther(
            (o.totalAmt - protocolfee - o.exchange.paymentAmt - o.prePayment.paymentAmt - o.refererrAmt) *
                amount -
                p.paymentAmt,
            msg.sender
        );
    } else {
        payEther(
            (o.totalAmt - protocolfee - o.exchange.paymentAmt - o.prePayment.paymentAmt) * amount - p.paymentAmt,
            msg.sender
        );
    }
```

Say, if `amount = 6`, while `((o.totalAmt * 50) / 10000) = 1 ETH`, `6 ETH` is total `protocolfee` and needs to be removed from `o.totalAmt * 6` to calculate taker’s part, while `1 ETH * 6 * 6 = 36 ETH` is actually removed in the calculation, i.e. `36 - 6 = 30 ETH` of taker’s funds will be frozen on the contract balance.

## Recommendation

Consider accounting for `amount` once, for example:
```solidity
function _settleBalances(
    Order calldata o,
    uint256 amount,
    address referrer,
    Payment calldata p
) internal {
    uint256 protocolfee = ((o.totalAmt * 50) / 10000);
    WETH.transferFrom(o.signer, address(this), o.totalAmt * amount);
    WETH.withdraw(o.totalAmt * amount);
    payEther(protocolfee * amount, address(distributor));
    payEther(o.exchange.paymentAmt * amount, o.exchange.paymentAddress);
    payEther(o.prePayment.paymentAmt * amount, o.prePayment.paymentAddress);
    if (o.refererrAmt > 0 && referrer != address(0)) {
        payEther(o.refererrAmt * amount, referrer);
        payEther(
            (o.totalAmt - protocolfee - o.exchange.paymentAmt - o.prePayment.paymentAmt - o.refererrAmt) *
                amount -
                p.paymentAmt,
            msg.sender
        );
    } else {
        payEther(
            (o.totalAmt - protocolfee - o.exchange.paymentAmt - o.prePayment.paymentAmt) * amount - p.paymentAmt,
            msg.sender
        );
    }
    payEther(p.paymentAmt, p.paymentAddress);
    distributor.addFee([msg.sender, o.exchange.paymentAddress], protocolfee * amount);
}
```

Resolved <https://github.com/golom-protocol/contracts/commit/366c0455547041003c28f21b9afba48dc33dc5c7#diff-63895480b947c0761eff64ee21deb26847f597ebee3c024fb5aa3124ff78f6ccR390>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the settlement routine that distributes proceeds after a NFT sale. When the contract processes a batch of NFTs (the `amount` parameter greater than one), it calculates the protocol fee as a percentage of the order total, but then multiplies that fee by the batch size twice: once when the fee amount is stored in a local variable and again when the fee is subtracted from the total payable to the taker. This double‑counting of the protocol fee leads to an excessive deduction from the taker’s share. For example, if the fee per unit is 1 ETH and six units are sold, the contract should remove only 6 ETH from the taker’s payout, but the erroneous formula removes 1 ETH × 6 × 6 = 36 ETH, freezing the extra 30 ETH in the contract balance. The root cause is an arithmetic mistake where the `amount` multiplier is applied to the protocol‑fee term both inside the fee variable and again inside the final payout expression. The bug can be exploited by anyone who can track the contract state and withdraw the surplus balance that remains unintentionally locked, effectively stealing the funds that should have gone to the seller. The impact is a reduction of the taker’s expected proceeds, causing funds to disappear from the user’s perspective; a seller who expects to receive the full net amount after fees may instead receive a smaller amount or, in extreme cases, nothing at all. The condition under which the issue manifests is any sale where `amount > 1`, i.e., batch sales or multiple‑unit fills. The affected parties are the buyers/takers of NFTs and, indirectly, any participants relying on the protocol’s accounting integrity. The problem was uncovered during a Code4rena audit by reviewing the `_settleBalances` implementation and noticing the mismatched arithmetic. It is subtle because the fee formula looks syntactically correct and only deviates when larger batch sizes are used, making it easy to miss in basic tests. To remediate, the protocol fee should be calculated once and multiplied by `amount` only a single time, and the taker payout formula should subtract exactly that fee quantity, not an amount‑scaled version of it. This belongs to the broader class of fee‑miscalculation bugs where fees are double‑counted or incorrectly scaled, leading to accounting errors and unintended fund lock‑up.
