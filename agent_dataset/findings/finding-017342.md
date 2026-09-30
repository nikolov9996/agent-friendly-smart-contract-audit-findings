---
id: 17342
severity: "High"
---

# Incorrect calculation of new price while adding position

## Description

The formula used for calculating `_newPrice` in `addToPosition()` function of Trading.sol is not correct, users will lose part of their funds/profit while using this function.

The wrong formula

```solidity
uint _newPrice = _trade.price*_trade.margin/_newMargin + _price*_addMargin/_newMargin;
```

The correct formula is

```solidity
uint _newPrice = _trade.price * _price * _newMargin /  (_trade.margin * _price + _addMargin * _trade.price);
```

Why this works?

Given

```
P1 = _trade.price
P2 = _price
P = _newPrice
M1 = _trade.margin
M2 = _addMargin
M =  M1 + M2 = _newMargin
L = _trade.leverage
U1 = M1 * L  = old position in USD
U2 = M2 * L = new position in USD
U = U1 + U2 = total position in USD
E1 = U1 / P1 = old position of base asset, such as ETH, of the pair
E2 = U2 / P2 = new position of base asset of the pair
E = E1 + E2 = total position of base asset of the pair
```

Then

```
P = U / E
  = (U1 + U2) / (E1 + E2)
  = (M1 * L + M2 * L) / (U1 / P1 + U2 / P2)
  = P1 * P2 * (M1 * L + M2 * L) / (U1 * P2 + U2 * P1)
  = P1 * P2 * (M1 + M2) * L / (M1 * L * P2 + M2 * L * P1)
  = P1 * P2 * (M1 + M2) * L / [(M1 * P2 + M2 * P1) * L]
  = P1 * P2 * M / (M1 * P2 + M2 * P1)
```

proven.

## Proof of Concept

The following test case shows two examples that users lose some funds due to adding a new position whenever their existing position is in profit or loss state.

```solidity
const { expect } = require("chai");
const { deployments, ethers, waffle } = require("hardhat");
const { parseEther, formatEther } = ethers.utils;
const { signERC2612Permit } = require('eth-permit');
const exp = require("constants");

describe("Incorrect calculation of new margin price while adding position", function () {
  let owner;
  let node;
  let user;
  let node2;
  let node3;
  let proxy;

  let Trading;
  let trading;

  let TradingExtension;
  let tradingExtension;

  let TradingLibrary;
  let tradinglibrary;

  let StableToken;
  let stabletoken;

  let StableVault;
  let stablevault;

  let position;

  let pairscontract;
  let referrals;

  let permitSig;
  let permitSigUsdc;

  let MockDAI;
  let mockdai;
  let MockUSDC;
  let mockusdc;

  let badstablevault;

  let chainlink;

  beforeEach(async function () {
    await deployments.fixture(['test']);
    [owner, node, user, node2, node3, proxy] = await ethers.getSigners();
    StableToken = await deployments.get("StableToken");
    stabletoken = await ethers.getContractAt("StableToken", StableToken.address);
    Trading = await deployments.get("Trading");
    trading = await ethers.getContractAt("Trading", Trading.address);
    await trading.connect(owner).setMaxWinPercent(5e10);
    TradingExtension = await deployments.get("TradingExtension");
    tradingExtension = await ethers.getContractAt("TradingExtension", TradingExtension.address);
    const Position = await deployments.get("Position");
    position = await ethers.getContractAt("Position", Position.address);
    MockDAI = await deployments.get("MockDAI");
    mockdai = await ethers.getContractAt("MockERC20", MockDAI.address);
    MockUSDC = await deployments.get("MockUSDC");
    mockusdc = await ethers.getContractAt("MockERC20", MockUSDC.address);
    const PairsContract = await deployments.get("PairsContract");
    pairscontract = await ethers.getContractAt("PairsContract", PairsContract.address);
    const Referrals = await deployments.get("Referrals");
    referrals = await ethers.getContractAt("Referrals", Referrals.address);
    StableVault = await deployments.get("StableVault");
    stablevault = await ethers.getContractAt("StableVault", StableVault.address);
    await stablevault.connect(owner).listToken(MockDAI.address);
    await stablevault.connect(owner).listToken(MockUSDC.address);
    await tradingExtension.connect(owner).setAllowedMargin(StableToken.address, true);
    await tradingExtension.connect(owner).setMinPositionSize(StableToken.address, parseEther("1"));
    await tradingExtension.connect(owner).setNode(node.address, true);
    await tradingExtension.connect(owner).setNode(node2.address, true);
    await tradingExtension.connect(owner).setNode(node3.address, true);
    await network.provider.send("evm_setNextBlockTimestamp", [2000000000]);
    await network.provider.send("evm_mine");
    permitSig = await signERC2612Permit(owner, MockDAI.address, owner.address, Trading.address, ethers.constants.MaxUint256);
    permitSigUsdc = await signERC2612Permit(owner, MockUSDC.address, owner.address, Trading.address, ethers.constants.MaxUint256);

    const BadStableVault = await ethers.getContractFactory("BadStableVault");
    badstablevault = await BadStableVault.deploy(StableToken.address);

    const ChainlinkContract = await ethers.getContractFactory("MockChainlinkFeed");
    chainlink = await ChainlinkContract.deploy();

    TradingLibrary = await deployments.get("TradingLibrary");
    tradinglibrary = await ethers.getContractAt("TradingLibrary", TradingLibrary.address);
    await trading.connect(owner).setLimitOrderPriceRange(1e10);
  });

  describe("Initial margin $500, leverage 2x, position $1000, price $1000", function () {
    let orderId;
    let initPrice = parseEther("1000");
    beforeEach(async function () {
      // To simpliy the problem, set fees to 0
      await trading.setFees(true, 0, 0, 0, 0, 0);
      await trading.setFees(false, 0, 0, 0, 0, 0);

      let TradeInfo = [parseEther("500"), MockDAI.address, StableVault.address, parseEther("2"), 1, true, parseEther("0"), parseEther("0"), ethers.constants.HashZero];
      let PriceData = [node.address, 1, initPrice, 0, 2000000000, false];
      let message = ethers.utils.keccak256(
        ethers.utils.defaultAbiCoder.encode(
          ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'bool'],
          [node.address, 1, initPrice, 0, 2000000000, false]
        )
      );
      let sig = await node.signMessage(
        Buffer.from(message.substring(2), 'hex')
      );
      
      let PermitData = [permitSig.deadline, ethers.constants.MaxUint256, permitSig.v, permitSig.r, permitSig.s, true];
      orderId = await position.getCount();
      await trading.connect(owner).initiateMarketOrder(TradeInfo, PriceData, sig, PermitData, owner.address);
      expect(await position.assetOpenPositionsLength(1)).to.equal(1);
      let trade = await position.trades(orderId);
      let marginAfterFee = trade.margin;
      expect(marginAfterFee.eq(parseEther('500'))).to.equal(true);
      expect(trade.price.eq(parseEther('1000'))).to.be.true;
      expect(trade.leverage.eq(parseEther('2'))).to.be.true;
    });

    it.only("Add position with new price $2000 and new margin $500, expected PnL payout $2000, actual payout $1666", async function () {
      // The price increases from $1000 to $2000, the old position earns $1000 profit.
      // The expected PnL payout = old margin + earned profit + new margin
      //                         = $500 + $1000 + $500
      //                         = $2000
      let addingPrice = parseEther('2000');
      let addingPriceData = [node.address, 1, addingPrice, 0, 2000000000, false];
      let addingMessage = ethers.utils.keccak256(
        ethers.utils.defaultAbiCoder.encode(
          ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'bool'],
          [node.address, 1, addingPrice, 0, 2000000000, false]
        )
      );
      let addingSig = await node.signMessage(
        Buffer.from(addingMessage.substring(2), 'hex')
      );

      let PermitData = [permitSig.deadline, ethers.constants.MaxUint256, permitSig.v, permitSig.r, permitSig.s, false];
      await trading.connect(owner).addToPosition(orderId, parseEther('500'), addingPriceData, addingSig, StableVault.address, MockDAI.address, PermitData, owner.address);

      let trade = await position.trades(orderId);
      let pnl = await tradinglibrary.pnl(trade.direction, addingPrice, trade.price,
        trade.margin, trade.leverage, trade.accInterest);
      expect(pnl._payout.gt(parseEther('1666'))).to.be.true;
      expect(pnl._payout.lt(parseEther('1667'))).to.be.true;
    });

    it.only("Add position with new price $750 and new margin $500, expected PnL payout $750, actual payout $714", async function () {
      // The price decreases from $1000 to $750, the old position losses $250.
      // The expected PnL payout = old margin - loss + new margin
      //                         = $500 - $250 + $500
      //                         = $750
      let addingPrice = parseEther('750');
      let addingPriceData = [node.address, 1, addingPrice, 0, 2000000000, false];
      let addingMessage = ethers.utils.keccak256(
        ethers.utils.defaultAbiCoder.encode(
          ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'bool'],
          [node.address, 1, addingPrice, 0, 2000000000, false]
        )
      );
      let addingSig = await node.signMessage(
        Buffer.from(addingMessage.substring(2), 'hex')
      );

      let PermitData = [permitSig.deadline, ethers.constants.MaxUint256, permitSig.v, permitSig.r, permitSig.s, false];
      await trading.connect(owner).addToPosition(orderId, parseEther('500'), addingPriceData, addingSig, StableVault.address, MockDAI.address, PermitData, owner.address);

      let trade = await position.trades(orderId);
      let pnl = await tradinglibrary.pnl(trade.direction, addingPrice, trade.price,
        trade.margin, trade.leverage, trade.accInterest);
      expect(pnl._payout.gt(parseEther('714'))).to.be.true;
      expect(pnl._payout.lt(parseEther('715'))).to.be.true;
    });

  });
});
```

The test result

```
Incorrect calculation of new margin price while adding position
    Initial margin $500, leverage 2x, position $1000, price $1000
      √ Add position with new price $2000 and new margin $500, expected PnL payout $2000, actual payout $1666
      √ Add position with new price $750 and new margin $500, expected PnL payout $750, actual payout $714
```

## Recommendation

Use the correct formula, the following test case is for the same above examples after fix.

```solidity
const { expect } = require("chai");
const { deployments, ethers, waffle } = require("hardhat");
const { parseEther, formatEther } = ethers.utils;
const { signERC2612Permit } = require('eth-permit');
const exp = require("constants");

describe("Correct calculation of new margin price while adding position", function () {
  let owner;
  let node;
  let user;
  let node2;
  let node3;
  let proxy;

  let Trading;
  let trading;

  let TradingExtension;
  let tradingExtension;

  let TradingLibrary;
  let tradinglibrary;

  let StableToken;
  let stabletoken;

  let StableVault;
  let stablevault;

  let position;

  let pairscontract;
  let referrals;

  let permitSig;
  let permitSigUsdc;

  let MockDAI;
  let mockdai;
  let MockUSDC;
  let mockusdc;

  let badstablevault;

  let chainlink;

  beforeEach(async function () {
    await deployments.fixture(['test']);
    [owner, node, user, node2, node3, proxy] = await ethers.getSigners();
    StableToken = await deployments.get("StableToken");
    stabletoken = await ethers.getContractAt("StableToken", StableToken.address);
    Trading = await deployments.get("Trading");
    trading = await ethers.getContractAt("Trading", Trading.address);
    await trading.connect(owner).setMaxWinPercent(5e10);
    TradingExtension = await deployments.get("TradingExtension");
    tradingExtension = await ethers.getContractAt("TradingExtension", TradingExtension.address);
    const Position = await deployments.get("Position");
    position = await ethers.getContractAt("Position", Position.address);
    MockDAI = await deployments.get("MockDAI");
    mockdai = await ethers.getContractAt("MockERC20", MockDAI.address);
    MockUSDC = await deployments.get("MockUSDC");
    mockusdc = await ethers.getContractAt("MockERC20", MockUSDC.address);
    const PairsContract = await deployments.get("PairsContract");
    pairscontract = await ethers.getContractAt("PairsContract", PairsContract.address);
    const Referrals = await deployments.get("Referrals");
    referrals = await ethers.getContractAt("Referrals", Referrals.address);
    StableVault = await deployments.get("StableVault");
    stablevault = await ethers.getContractAt("StableVault", StableVault.address);
    await stablevault.connect(owner).listToken(MockDAI.address);
    await stablevault.connect(owner).listToken(MockUSDC.address);
    await tradingExtension.connect(owner).setAllowedMargin(StableToken.address, true);
    await tradingExtension.connect(owner).setMinPositionSize(StableToken.address, parseEther("1"));
    await tradingExtension.connect(owner).setNode(node.address, true);
    await tradingExtension.connect(owner).setNode(node2.address, true);
    await tradingExtension.connect(owner).setNode(node3.address, true);
    await network.provider.send("evm_setNextBlockTimestamp", [2000000000]);
    await network.provider.send("evm_mine");
    permitSig = await signERC2612Permit(owner, MockDAI.address, owner.address, Trading.address, ethers.constants.MaxUint256);
    permitSigUsdc = await signERC2612Permit(owner, MockUSDC.address, owner.address, Trading.address, ethers.constants.MaxUint256);

    const BadStableVault = await ethers.getContractFactory("BadStableVault");
    badstablevault = await BadStableVault.deploy(StableToken.address);

    const ChainlinkContract = await ethers.getContractFactory("MockChainlinkFeed");
    chainlink = await ChainlinkContract.deploy();

    TradingLibrary = await deployments.get("TradingLibrary");
    tradinglibrary = await ethers.getContractAt("TradingLibrary", TradingLibrary.address);
    await trading.connect(owner).setLimitOrderPriceRange(1e10);
  });

  describe("Initial margin $500, leverage 2x, position $1000, price $1000", function () {
    let orderId;
    let initPrice = parseEther("1000");
    beforeEach(async function () {
      // To simpliy the problem, set fees to 0
      await trading.setFees(true, 0, 0, 0, 0, 0);
      await trading.setFees(false, 0, 0, 0, 0, 0);

      let TradeInfo = [parseEther("500"), MockDAI.address, StableVault.address, parseEther("2"), 1, true, parseEther("0"), parseEther("0"), ethers.constants.HashZero];
      let PriceData = [node.address, 1, initPrice, 0, 2000000000, false];
      let message = ethers.utils.keccak256(
        ethers.utils.defaultAbiCoder.encode(
          ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'bool'],
          [node.address, 1, initPrice, 0, 2000000000, false]
        )
      );
      let sig = await node.signMessage(
        Buffer.from(message.substring(2), 'hex')
      );
      
      let PermitData = [permitSig.deadline, ethers.constants.MaxUint256, permitSig.v, permitSig.r, permitSig.s, true];
      orderId = await position.getCount();
      await trading.connect(owner).initiateMarketOrder(TradeInfo, PriceData, sig, PermitData, owner.address);
      expect(await position.assetOpenPositionsLength(1)).to.equal(1);
      let trade = await position.trades(orderId);
      let marginAfterFee = trade.margin;
      expect(marginAfterFee.eq(parseEther('500'))).to.equal(true);
      expect(trade.price.eq(parseEther('1000'))).to.be.true;
      expect(trade.leverage.eq(parseEther('2'))).to.be.true;
    });

    it.only("Add position with new price $2000 and new margin $500, expected PnL payout $2000, actual payout $1999.99999", async function () {
      // The price increases from $1000 to $2000, the old position earns $1000 profit.
      // The expected PnL payout = old margin + earned profit + new margin
      //                         = $500 + $1000 + $500
      //                         = $2000
      let addingPrice = parseEther('2000');
      let addingPriceData = [node.address, 1, addingPrice, 0, 2000000000, false];
      let addingMessage = ethers.utils.keccak256(
        ethers.utils.defaultAbiCoder.encode(
          ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'bool'],
          [node.address, 1, addingPrice, 0, 2000000000, false]
        )
      );
      let addingSig = await node.signMessage(
        Buffer.from(addingMessage.substring(2), 'hex')
      );

      let PermitData = [permitSig.deadline, ethers.constants.MaxUint256, permitSig.v, permitSig.r, permitSig.s, false];
      await trading.connect(owner).addToPosition(orderId, parseEther('500'), addingPriceData, addingSig, StableVault.address, MockDAI.address, PermitData, owner.address);

      let trade = await position.trades(orderId);
      let pnl = await tradinglibrary.pnl(trade.direction, addingPrice, trade.price,
        trade.margin, trade.leverage, trade.accInterest);
      expect(pnl._payout.gt(parseEther('1999.99999'))).to.be.true;
      expect(pnl._payout.lt(parseEther('2000'))).to.be.true;
    });

    it.only("Add position with new price $750 and new margin $500, expected PnL payout $750, actual payout $749.99999", async function () {
      // The price decreases from $1000 to $750, the old position losses $250.
      // The expected PnL payout = old margin - loss + new margin
      //                         = $500 - $250 + $500
      //                         = $750
      let addingPrice = parseEther('750');
      let addingPriceData = [node.address, 1, addingPrice, 0, 2000000000, false];
      let addingMessage = ethers.utils.keccak256(
        ethers.utils.defaultAbiCoder.encode(
          ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'bool'],
          [node.address, 1, addingPrice, 0, 2000000000, false]
        )
      );
      let addingSig = await node.signMessage(
        Buffer.from(addingMessage.substring(2), 'hex')
      );

      let PermitData = [permitSig.deadline, ethers.constants.MaxUint256, permitSig.v, permitSig.r, permitSig.s, false];
      await trading.connect(owner).addToPosition(orderId, parseEther('500'), addingPriceData, addingSig, StableVault.address, MockDAI.address, PermitData, owner.address);

      let trade = await position.trades(orderId);
      let pnl = await tradinglibrary.pnl(trade.direction, addingPrice, trade.price,
        trade.margin, trade.leverage, trade.accInterest);
      expect(pnl._payout.gt(parseEther('749.99999'))).to.be.true;
      expect(pnl._payout.lt(parseEther('750'))).to.be.true;
    });

  });
});
```

The test result

```
Correct calculation of new margin price while adding position
    Initial margin $500, leverage 2x, position $1000, price $1000
      √ Add position with new price $2000 and new margin $500, expected PnL payout $2000, actual payout $1999.99999
      √ Add position with new price $750 and new margin $500, expected PnL payout $750, actual payout $749.99999
```

The warden has shown how, using `addToPosition` can cause the payout math to become incorrect, because this highlights an issue with the math of the protocol, which will impact its functionality, I believe High Severity to be appropriate.

**[GainsGoblin (Tigris Trade) resolved](https://github.com/code-423n4/2022-12-tigris-findings/issues/236#issuecomment-1407511530):**

Mitigation: <https://github.com/code-423n4/2022-12-tigris/pull/2#issuecomment-1419174986>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the addToPosition function of the Trading contract where the new average entry price for a leveraged position is calculated with an incorrect arithmetic formula. Instead of using a weighted harmonic average that reflects the total USD exposure divided by the total base‑asset amount, the code combines the old price and the new price linearly weighted by their respective margins. This mis‑calculation causes the resulting _newPrice to be slightly lower than it should be, which in turn reduces the payout that traders receive when they add additional margin to an existing position. The root cause is a faulty algebraic expression: _newPrice = oldPrice * oldMargin / newMargin + newPrice * addedMargin / newMargin, which does not preserve the invariant that total position value equals the sum of individual sub‑positions. The correct expression is _newPrice = oldPrice * newPrice * totalMargin / (oldMargin * newPrice + addedMargin * oldPrice). The bug manifests whenever a trader calls addToPosition with a non‑zero additional margin, regardless of whether the market price moves up or down. Exploitation is straightforward: an attacker can repeatedly add margin to a position and systematically receive a payout that is marginally less than the mathematically expected amount, leading to a gradual erosion of funds. In practice users observe that after adding margin their profit or refund is off by a few wei (for example, a payout of 1999.99999 instead of the expected 2000), or that the balance displayed in the UI is lower than anticipated. The impact is a loss of user funds and a breach of the protocol’s accounting guarantees, as the total position value no longer matches the sum of its components. This issue affects any participant who uses the addToPosition feature, including regular traders and liquidity providers, and it undermines confidence in the platform’s financial correctness. The problem was discovered during a security audit when unit tests compared expected PnL outcomes with actual contract results and identified consistent under‑payment. The discrepancy is subtle because the error is small and can be mistaken for normal rounding, making it hard to detect without precise testing. To remediate the issue, the contract must replace the faulty formula with the mathematically correct one that computes the new average price as the product of the old and new prices multiplied by the total margin, divided by the sum of the cross‑products of margins and opposite prices. This change restores proper accounting, ensures that added margin does not unintentionally diminish user payouts, and aligns the contract with standard financial math practices. The vulnerability belongs to the class of financial‑logic arithmetic bugs, specifically incorrect weighted‑average calculations that violate expected invariants in leveraged trading systems.
