---
id: 25747
severity: "Crit/High"
---

# Users will lock raffle prizes on the WinnablesPrizeManager contract by calling WinnablesTicketManager::propagateRaffleWinner with wrong CCIP inputs

## Description



## Proof of Concept

The test below, which is an edited version of [this existing test](<https://github.com/sherlock-audit/2024-08-winnables-raffles/blob/main/public-contracts/test/TicketManager.js#L786>), shows that the function call will be successful with a random chainSelector

```javascript
    it('Should be able to propagate when the winner is drawn', async () => {
@>    const { events } = await (await manager.propagateRaffleWinner(counterpartContractAddress, 9846, 1)).wait();
      expect(events).to.have.lengthOf(3);
      const ccipEvent = ccipRouter.interface.parseLog(events[0]);
      expect(ccipEvent.args.receiver).to.eq('0x' + counterpartContractAddress.toLowerCase().slice(-40).padStart(64, '0'));
      expect(ccipEvent.args.data).to.have.lengthOf(108);
      const drawnWinner = ethers.utils.getAddress('0x' + ccipEvent.args.data.slice(-40));
      expect(buyers.find(b => b.address === drawnWinner)).to.not.be.undefined;
      expect(ccipEvent.args.data.slice(0, 68)).to.eq('0x010000000000000000000000000000000000000000000000000000000000000001');
    });
```

## Recommendation

Implement input validation to ensure that `prizeManager` and `chainSelector` are correct before proceeding with the propagation.
