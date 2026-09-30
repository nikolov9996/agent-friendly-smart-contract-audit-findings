---
id: 11761
severity: "High"
---

# Accumulated ETH fees of InfinityExchange cannot be retrieved

## Description

ETH fees accumulated from takeOrders() and takeMultipleOneOrders() operations are permanently frozen within the contract as there is only one way designed to retrieve them, a rescueETH() function, and it will work as intended, not being able to access ETH balance of the contract.

Setting the severity as high as the case is a violation of system’s core logic and a permanent freeze of ETH revenue of the project.

## Proof of Concept

Fees are accrued in user-facing takeOrders() and takeMultipleOneOrders via the following call sequences:

    takeOrders -> _takeOrders -> _execTakeOrders -> _transferNFTsAndFees -> _transferFees
    takeMultipleOneOrders -> _execTakeOneOrder -> _transferNFTsAndFees -> _transferFees

While token fees are transferred right away, ETH fees are kept with the InfinityExchange contract:

```solidity
/**
 * @notice Transfer fees. Fees are always transferred from buyer to the seller and the exchange although seller is 
          the one that actually 'pays' the fees
 * @dev if the currency ETH, no additional transfer is needed to pay exchange fees since the contract is 'payable'
 * @param seller the seller
 * @param buyer the buyer
 * @param amount amount to transfer
 * @param currency currency of the transfer
 */
function _transferFees(
  address seller,
  address buyer,
  uint256 amount,
  address currency
) internal {
  // protocol fee
  uint256 protocolFee = (PROTOCOL_FEE_BPS * amount) / 10000;
  uint256 remainingAmount = amount - protocolFee;
  // ETH
  if (currency == address(0)) {
    // transfer amount to seller
    (bool sent, ) = seller.call{value: remainingAmount}('');
    require(sent, 'failed to send ether to seller');
```

i.e. when `currency` is ETH the fee part of the amount, `protocolFee`, is left with the InfinityExchange contract.

The only way to retrieve ETH from the contract is rescueETH() function:

```solidity
/// @dev used for rescuing exchange fees paid to the contract in ETH
function rescueETH(address destination) external payable onlyOwner {
  (bool sent, ) = destination.call{value: msg.value}('');
  require(sent, 'failed');
}
```

However, it cannot reach ETH on the contract balance as `msg.value` is used as the amount to be sent over. I.e. only ETH attached to the rescueETH() call is transferred from `owner` to `destination`. ETH funds that InfinityExchange contract holds remain inaccessible.

## Recommendation

Consider adding contract balance to the funds transferred:

```solidity
/// @dev used for rescuing exchange fees paid to the contract in ETH
function rescueETH(address destination) external payable onlyOwner {
  (bool sent, ) = destination.call{value: address(this).balance}('');
  require(sent, 'failed');
}
```

When an order is filled using ETH, the exchange collects fees by holding them in the contract for later withdraw. However the only withdraw mechanism does not work so that ETH becomes trapped forever.

This is a High risk issue since some ETH is lost with each ETH based trade.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The InfinityExchange contract accumulates protocol fees in ETH whenever a trade is settled with Ether as the payment currency. During fee handling the protocol portion of the trade amount, called protocolFee, is deliberately left in the contract while the remainder is sent to the seller. The contract includes a rescueETH() function that owners can call to retrieve these fees. However, the implementation of rescueETH() mistakenly forwards only the Ether supplied with the rescueETH() call (msg.value) to the destination address, instead of the Ether that actually resides in the contract’s balance (address(this).balance). As a result, the accrued ETH fees remain locked inside the contract forever because there is no code path that can move the stored balance out. The bug is a classic example of an "incorrect withdrawal amount" or "funds‑trapping" vulnerability, where the withdrawal routine uses the wrong source of funds. It can be exploited simply by invoking rescueETH() – the call will succeed, but the contract’s fee balance will stay unchanged, effectively causing permanent loss of revenue. Users and protocol owners who expect to collect the accumulated fees see no change in the contract’s ETH holdings; UI elements may report fees collected while the actual withdrawable amount is zero, leading to confusion and a perception that funds have vanished. The issue occurs whenever the exchange processes ETH‑based orders, which is the normal operating condition for the protocol. All participants – traders, liquidity providers, and especially the contract owner – are affected because the protocol’s primary revenue stream becomes inaccessible. The problem was identified during a security audit that inspected the fee‑handling logic and the rescue function, noticing that msg.value is unrelated to the contract’s stored balance. It is hard to notice because the rescueETH() function appears to provide a withdrawal mechanism, yet it never actually accesses the contract’s Ether. To remediate, the rescue function should be rewritten to forward address(this).balance (or a specified amount) instead of msg.value, ensuring that the accumulated fees can be transferred out. Conceptually, any contract that holds native tokens must use its own balance as the source for withdrawals, not the caller‑supplied value, to avoid permanent fund lock.
