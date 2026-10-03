---
id: 25749
severity: "Crit/High"
---

# Method refundPlayers doesn't update _lockedETH in WinnableTicketManager

## Description



## Proof of Concept

Add the following snippet in `/test/TicketManager.js`

```javascript
it('Should be able to refund tickets purchased', async () => {
  const contractBalanceBefore = await ethers.provider.getBalance(manager.address);
  const userBalanceBefore = await ethers.provider.getBalance(buyer2.address);
  let lockedETH = await manager.getLockedEth()
  console.log("Locked ETH is: ", lockedETH)
  const tx = await manager.refundPlayers(1, [buyer2.address]);
  lockedETH = await manager.getLockedEth()
  console.log("Locked ETH after player unlock is: ", lockedETH)
  const { events } = await tx.wait();
  expect(events).to.have.lengthOf(1);
  const [ event ] = events;
  expect(event.event).to.equal('PlayerRefund');
  const contractBalanceAfter = await ethers.provider.getBalance(manager.address);
  const userBalanceAfter = await ethers.provider.getBalance(buyer2.address);
  expect(contractBalanceAfter).to.eq(contractBalanceBefore.sub(100));
  expect(userBalanceAfter).to.eq(userBalanceBefore.add(100));
  const { withdrawn } = await manager.getParticipation(1, buyer2.address);
  expect(withdrawn).to.eq(true);
});
```

## Impact

It leads to locking of ETH(AVAX) in the contract forever that was protocol income.

## Recommendation

Update the _lockedETH variable in `refundPlayers()` as below:

```solidity
function refundPlayers(uint256 raffleId, address[] calldata players) external {
    Raffle storage raffle = _raffles[raffleId];
    if (raffle.status != RaffleStatus.CANCELED) revert InvalidRaffle();
    for (uint256 i = 0; i < players.length; ) {
        address player = players[i];
        uint256 participation = uint256(raffle.participations[player]);
        if (((participation >> 160) & 1) == 1) revert PlayerAlreadyRefunded(player);
        raffle.participations[player] = bytes32(participation | (1 << 160));
        uint256 amountToSend = (participation & type(uint128).max);
        _lockedETH -= amountToSend;
        _sendETH(amountToSend, player);
        emit PlayerRefund(raffleId, player, bytes32(participation));
        unchecked { ++i; }
    }
}
```
